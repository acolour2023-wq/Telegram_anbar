import os
import glob
import sys
import unicodedata
import urllib.parse
import time
import datetime
import shutil
import base64
import subprocess
import threading
import requests
import pandas as pd
import telebot
from telebot import types

# Windows konsolunda UTF-8 və emoji dəstəyini təmin edirik
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_print(*args, **kwargs):
    """Konsola UTF-8 və emoji simvollarını təhlükəsiz şəkildə yazan funksiya"""
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            clean_args = [str(a).encode('ascii', 'replace').decode('ascii') for a in args]
            print(*clean_args, **kwargs)
        except Exception:
            pass

# .env faylını oxuyub mühit dəyişənlərinə yükləyirik
def load_env_file():
    """Mövcud .env faylındakı dəyişənləri os.environ-a yükləyir"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            safe_print(f"⚠️ .env oxunarkən xəta: {e}")

load_env_file()

# --- 1. AYARLAR ---
TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    or os.environ.get("BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or os.environ.get("TOKEN")
    or ""
).strip().strip('"').strip("'")
if not TELEGRAM_TOKEN:
    safe_print("⚠️ DİQQƏT: TELEGRAM_TOKEN tapılmadı! Zəhmət olmasa .env faylında TELEGRAM_TOKEN təyin edin.")
tg_bot = telebot.TeleBot(TELEGRAM_TOKEN or "0000000000:AA_NO_TOKEN_PROVIDED_IN_ENV")

# Admin və Təhlükəsizlik Ayarları
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "anbar2026").strip() or "anbar2026"
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# GitHub Avtomatik Sinxronizasiya (Render üçün)
GITHUB_REPO = os.environ.get("GITHUB_REPO", "acolour2023-wq/Telegram_anbar")
GITHUB_TOKEN = (
    os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GITHUBTOKEN")
    or os.environ.get("GH_TOKEN")
    or ""
).strip()

# Təsdiq gözləyən fayl yeniləmələri (user_id -> info)
PENDING_UPLOADS = {}

# Təsdiq gözləyən qrup elanları (user_id -> info)
PENDING_ANNOUNCEMENTS = {}

# Çatda göndərilən və izlənən mesaj ID-ləri (chat_id -> [message_id, ...])
CHAT_MESSAGES = {}

# İnteraktiv Vərəqləmə (Pagination) axtarış sessiyaları (session_id -> data)
SEARCH_SESSIONS = {}

# Təkrar axtarışları izləmək üçün (chat_id:query_norm -> {"user_name": ..., "time": ...})
RECENT_QUERIES = {}

# Barkod Kamera Skaneri WebApp URL (Render üzərindən)
SCANNER_URL = os.environ.get("SCANNER_URL", "https://telegram-anbar-11y6.onrender.com/scanner")

# Dore Group MMC Qrup ID-si (Səhər salamlama və bildirişlər üçün)
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-1003749180365")

# Dore Group MMC - Əlaqə və Şöbələr Məlumatı
CONTACTS_INFO = (
    "🏢 **DORE GROUP MMC — ƏLAQƏ VƏ ANBAR** 📞\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📦 **Anbar Müdiri / Təhvil-Təslim:**\n"
    "📞 `+994 70 806 03 13` *(Zəng üçün toxunun)*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📍 **Ünvan:** Gəncə şəhəri, Baş Anbar\n"
    "⏰ **İş rejimi:** 09:00 – 18:00 (Bazar ertəsi – Şənbə)"
)


# Keş (Cache) mexanizmi: Excel faylını RAM-da saxlamaq üçün
DATA_CACHE = {
    "df": None,
    "mtime": 0,
    "filepath": None
}



# --- 2. KÖMƏKÇİ FUNKSİYALAR ---
def auto_delete_message(chat_id, message_id, delay_seconds=5):
    """Müəyyən saniyə sonra mesajı avtomatik silən köməkçi funksiya"""
    time.sleep(delay_seconds)
    try:
        tg_bot.delete_message(chat_id, message_id)
    except Exception:
        pass

def is_user_admin(chat, user_id):
    """İstifadəçinin qrup admini olub-olmadığını yoxlayır"""
    if chat.type == "private":
        return True
    if user_id in ADMIN_IDS:
        return True
    try:
        member = tg_bot.get_chat_member(chat.id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception as e:
        safe_print(f"⚠️ Admin statusu yoxlanarkən xəta: {e}")
        return False

def safe_send_message(chat_id, text, reply_markup=None, thread_id=None, reply_to_message_id=None, track=True, parse_mode="Markdown"):
    """
    Təhlükəsiz mesaj göndərmə funksiyası.
    İstənilən Telegram API, şəbəkə, Markdown və ya mövzu (topic) xətasında dərhal fallback tətbiq edərək 
    istifadəçinin cavabsız qalmasının qarşısını alır.
    """
    if not text:
        return None
    
    sent_msg = None
    # 1-ci cəhd: Markdown formatı, Mövzu (thread_id) və Inline Markup düymələri ilə
    try:
        if reply_to_message_id:
            sent_msg = tg_bot.send_message(chat_id, text, reply_markup=reply_markup, message_thread_id=thread_id, reply_to_message_id=reply_to_message_id, parse_mode=parse_mode)
        else:
            sent_msg = tg_bot.send_message(chat_id, text, reply_markup=reply_markup, message_thread_id=thread_id, parse_mode=parse_mode)
    except Exception as e1:
        safe_print(f"⚠️ İlk mesaj göndərmə cəhdi (Markdown) uğursuz oldu: {e1}")

    # 2-ci cəhd: Formatlaşdırmasız (plain text) olaraq mövzuya göndərmə (Markdown xətalarına qarşı qoruma)
    if not sent_msg:
        try:
            if reply_to_message_id:
                sent_msg = tg_bot.send_message(chat_id, text, reply_markup=reply_markup, message_thread_id=thread_id, reply_to_message_id=reply_to_message_id)
            else:
                sent_msg = tg_bot.send_message(chat_id, text, reply_markup=reply_markup, message_thread_id=thread_id)
        except Exception as e2:
            safe_print(f"⚠️ Düz mətn göndərmə cəhdi uğursuz oldu: {e2}")

    # 3-cü cəhd: Birbaşa əsas çata düyməsiz və mövzusuz göndərmə (son çətir)
    if not sent_msg:
        try:
            sent_msg = tg_bot.send_message(chat_id, text)
        except Exception as e3:
            safe_print(f"❌ Mesaj heç bir yolla göndərilə bilmədi: {e3}")
            return None

    if sent_msg and track and hasattr(sent_msg, 'message_id'):
        CHAT_MESSAGES.setdefault(chat_id, []).append(sent_msg.message_id)
        if len(CHAT_MESSAGES[chat_id]) > 100:
            CHAT_MESSAGES[chat_id] = CHAT_MESSAGES[chat_id][-100:]

    return sent_msg

def morning_greeting_worker():
    """Hər səhər saat 09:00-da (Bakı vaxtı ilə UTC+4) qrupa salamlama və uğurlar mesajı göndərən arxa fon funksiyası"""
    safe_print("⏰ Səhər salamlama taymeri aktivdir (Hər səhər 09:00 - Bakı vaxtı ilə).")
    last_sent_date = None

    while True:
        try:
            # Bakı saat qurşağı (UTC+4)
            baku_tz = datetime.timezone(datetime.timedelta(hours=4))
            now_baku = datetime.datetime.now(baku_tz)
            today_str = now_baku.strftime("%Y-%m-%d")

            # Hər səhər 09:00 - 09:05 aralığında və bu gün göndərilməyibsə
            if now_baku.hour == 9 and now_baku.minute < 5 and last_sent_date != today_str:
                greeting_text = (
                    "🌅 **Sabahınız xeyir, Dore Group MMC komandası!** ☀️\n\n"
                    "💼 Hər birinizə uğurlu, bərəkətli və bol enerjili iş günü arzulayırıq! 🚀\n\n"
                    "📦 *Anbar botu aktivdir — məhsul qalığını və qiymətini öyrənmək üçün barkodun son 4 rəqəmini və ya adını yazmağınız kifayətdir.*"
                )

                target_id = GROUP_CHAT_ID
                try:
                    target_id = int(target_id)
                except Exception:
                    pass

                safe_print(f"📢 Səhər salamlama mesajı göndərilir: {target_id} ({today_str} 09:00)")
                sent = safe_send_message(target_id, greeting_text, track=False)
                if sent:
                    last_sent_date = today_str
                    safe_print(f"✅ Səhər salamlama mesajı qrupa uğurla çatdırıldı: {target_id}")
                else:
                    safe_print(f"⚠️ Səhər salamlama mesajı göndərilə bilmədi: {target_id}")

            time.sleep(25)
        except Exception as e:
            safe_print(f"⚠️ Səhər salamlama taymerində xəta: {e}")
            time.sleep(60)

def az_normalize(text):
    """
    Azərbaycan hərflərini və Unicode simvollarını axtarış üçün təmizləyir.
    Məsələn: 'NUR GİDA' -> 'nur gida', 'MƏHSUL' -> 'mehsul'
    """
    if not text:
        return ""
    tr_map = str.maketrans({
        'İ': 'i', 'I': 'ı', 'Ə': 'ə', 'Ş': 'ş', 'Ç': 'ç', 'Ğ': 'ğ', 'Ö': 'ö', 'Ü': 'ü'
    })
    s = str(text).translate(tr_map).lower()
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', s) if unicodedata.category(ch) != 'Mn')
    ascii_map = str.maketrans({
        'ı': 'i', 'ə': 'e', 'ş': 's', 'ç': 'c', 'ğ': 'g', 'ö': 'o', 'ü': 'u'
    })
    return s.translate(ascii_map).strip()

def sutun_temizle(c):
    """Sütun adlarını kiçik hərflərə çevirir və Unicode bələdçi simvollarını təmizləyir."""
    return az_normalize(c)

def fayli_tap():
    """Skriptin yerləşdiyi qovluqda müvafiq .xlsx faylını tapır."""
    current_folder = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(current_folder, "*.xlsx"))
    
    for f in files:
        fname = os.path.basename(f).lower()
        if "mehsul" in fname or "anbar" in fname:
            return f
            
    return files[0] if files else None

def datani_yukle():
    """
    Excel faylını yalnız dəyişiklik olduqda və ya ilk dəfə oxuyur.
    Bu keş mexanizmi axtarış sürətini ciddi şəkildə artırır.
    """
    fayl = fayli_tap()
    if not fayl:
        return None, "❌ Excel faylı tapılmadı! Xahiş olunur qovluğa .xlsx faylı əlavə edin."

    try:
        mtime = os.path.getmtime(fayl)
        
        if DATA_CACHE["df"] is not None and DATA_CACHE["mtime"] == mtime and DATA_CACHE["filepath"] == fayl:
            return DATA_CACHE["df"], None

        df = pd.read_excel(fayl, dtype=str).fillna("")
        DATA_CACHE["df"] = df
        DATA_CACHE["mtime"] = mtime
        DATA_CACHE["filepath"] = fayl
        safe_print(f"🔄 Excel yaddaşa yükləndi: {os.path.basename(fayl)} ({len(df)} sətir)")
        return df, None
    except Exception as e:
        safe_print(f"❌ Excel oxunma xətası: {e}")
        return None, f"❌ Fayl oxunarkən xəta baş verdi: {e}"

def temizle(deyer):
    """Məlumatları təmizləyir və '.0' / ',00' sonluqlarını təhlükəsiz şəkildə silir."""
    if pd.isna(deyer):
        return ""
    s = str(deyer).strip()
    if s.lower() in ["nan", "none", "null"]:
        return ""
    if s.endswith(',00') or s.endswith('.00'):
        s = s[:-3]
    elif s.endswith('.0') and s[:-2].replace('-', '').replace(',', '').isdigit():
        s = s[:-2]
    return s

def ana_menyu(is_private=False):
    """Botun əsas düymələr menyusu"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_anbar = types.KeyboardButton("📦 Anbar & Qiymət")
    if is_private:
        btn_scanner = types.KeyboardButton("📷 Barkod Skaneri", web_app=types.WebAppInfo(url=SCANNER_URL))
    else:
        btn_scanner = types.KeyboardButton("📷 Barkod Skaneri")
    btn_elan = types.KeyboardButton("📢 Qrupa Elan")
    btn_elaqe = types.KeyboardButton("☎️ Əlaqə & Şöbələr")
    btn_temizle = types.KeyboardButton("🧹 Çatı Təmizlə")
    btn_yaddas = types.KeyboardButton("🗑 Yaddaşı Təmizlə")
    markup.row(btn_anbar, btn_scanner)
    markup.row(btn_elan, btn_elaqe)
    markup.row(btn_temizle, btn_yaddas)
    return markup

def google_duymesi_duzelt(axtaris_metni):
    """Google Images (Şəkillər) axtarış linki olan Inline Düymə hazırlayır"""
    markup = types.InlineKeyboardMarkup()
    encoded_text = urllib.parse.quote(axtaris_metni)
    url = f"https://www.google.com/search?q={encoded_text}&tbm=isch"
    btn = types.InlineKeyboardButton("🖼️ Şəklə Bax (Google)", url=url)
    markup.add(btn)
    return markup

def build_pagination_markup(session_id, current_idx, total, google_markup=None):
    """Məhsul nəticələri üçün interaktiv vərəqləmə (pagination) və Google düyməsi hazırlayır"""
    markup = types.InlineKeyboardMarkup()
    prev_idx = (current_idx - 1) % total
    next_idx = (current_idx + 1) % total

    btn_prev = types.InlineKeyboardButton("⬅️ Əvvəlki", callback_data=f"nav:{session_id}:{prev_idx}")
    btn_count = types.InlineKeyboardButton(f"📄 {current_idx + 1} / {total}", callback_data="nav_noop")
    btn_next = types.InlineKeyboardButton("Növbəti ➡️", callback_data=f"nav:{session_id}:{next_idx}")
    markup.row(btn_prev, btn_count, btn_next)

    if google_markup and hasattr(google_markup, 'keyboard') and google_markup.keyboard:
        for row in google_markup.keyboard:
            markup.row(*row)

    return markup

def bazada_axtar(axtaris_cumlesi):
    """Bazada tam təhlükəsiz axtarış funksiyası. Həmişə (metn, markup) 2-tuple qaytarır."""
    try:
        df, err = datani_yukle()
        if err:
            return [(err, None)]

        raw_query = str(axtaris_cumlesi).strip()
        query_norm = az_normalize(raw_query)
        axtarilan_sozler = query_norm.split()

        if not axtarilan_sozler:
            return [("ℹ️ Xahiş olunur axtarış sözü daxil edin.", None)]

        safe_print(f"🔎 Axtarılır: '{raw_query}' (Norm: {axtarilan_sozler})")

        col_map = {c: sutun_temizle(c) for c in df.columns}

        kod_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['kod', 'code', 'id', 'nomer'])), None)
        ad_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['ad', 'name', 'mehsul', 'naim', 'tovar'])), None)
        qiymet_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['qiym', 'qym', 'price', 'cena', 'som'])), None)
        barkod_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['barkod', 'barcode', 'shtrih'])), None)
        brend_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['brend', 'brand', 'firma', 'marka'])), None)
        qalig_col = next((orig for orig, clean in col_map.items() if any(k in clean for k in ['qalig', 'qaliq', 'stok', 'say', 'miqdar', 'ostatok', 'count', 'qty'])), None)
        if not qalig_col:
            qalig_col = next((orig for orig, clean in col_map.items() if 'anbar' in clean), None)

        if not kod_col and not ad_col: 
            return [("❌ Excel faylında uyğun sütunlar ('KODU', 'ADI') tapılmadı.", None)]

        matches = []
        records = df.to_dict('records')
        is_digits = query_norm.isdigit()

        for row in records:
            db_kod = temizle(row.get(kod_col, "")) if kod_col else ""
            db_ad = str(row.get(ad_col, "")).strip() if ad_col else ""
            db_barkod = temizle(row.get(barkod_col, "")) if barkod_col else ""
            db_brend = str(row.get(brend_col, "")).strip() if brend_col else ""
            db_qalig = temizle(row.get(qalig_col, "")) if qalig_col else ""

            kod_norm = az_normalize(db_kod)
            barkod_norm = az_normalize(db_barkod)
            ad_norm = az_normalize(db_ad)
            brend_norm = az_normalize(db_brend)

            if is_digits:
                score = 0
                if barkod_norm == query_norm:
                    score = 100
                elif barkod_norm.endswith(query_norm):
                    score = 80
                else:
                    continue
                matches.append((score, row, db_kod, db_ad, db_barkod, db_brend, db_qalig))
            else:
                tam_setir = f"{kod_norm} {barkod_norm} {ad_norm} {brend_norm}"
                if all(soz in tam_setir for soz in axtarilan_sozler):
                    score = 0
                    if query_norm in ad_norm:
                        score += 40
                    if query_norm in brend_norm:
                        score += 30
                    matches.append((score, row, db_kod, db_ad, db_barkod, db_brend, db_qalig))

        if not matches:
            return [("❌ Uyğun məhsul tapılmadı.", None)]

        matches.sort(key=lambda x: x[0], reverse=True)

        neticeler = []
        toplam_say = len(matches)

        for score, row, db_kod, db_ad, db_barkod, db_brend, db_qalig in matches[:10]:
            qiymet_raw = str(row.get(qiymet_col, "0")).replace(',', '.') if qiymet_col else "0"
            try:
                qiymet_val = float(qiymet_raw)
                qiymet = f"{qiymet_val:.2f}"
            except Exception:
                qiymet = qiymet_raw

            goster_brend = db_brend if db_brend and db_brend.lower() != "nan" else "-"
            goster_barkod = db_barkod if db_barkod and db_barkod.lower() != "nan" else "-"
            goster_qalig = db_qalig if db_qalig and db_qalig.lower() != "nan" else "-"

            qalig_line = ""
            if qalig_col and goster_qalig != "-":
                try:
                    q_num = float(str(goster_qalig).replace(',', '.'))
                    if q_num <= 0:
                        qalig_line = "\n🔴 **Qalıq:** Bitib (0 ədəd)"
                    elif q_num <= 5:
                        qalig_line = f"\n🟡 **Qalıq:** {goster_qalig} ⚠️ *(Az qalıb!)*"
                    else:
                        qalig_line = f"\n🟢 **Qalıq:** {goster_qalig}"
                except Exception:
                    qalig_line = f"\n📊 **Qalıq:** {goster_qalig}"

            caption = (
                f"🆔 **Kod:** `{db_kod}`\n"
                f"📦 **Məhsul:** {db_ad}\n"
                f"🏷️ **Brend:** {goster_brend}\n"
                f"💵 **Qiymət:** **{qiymet} AZN**\n"
                f"📊 **Barkod:** `{goster_barkod}`"
                f"{qalig_line}"
            )

            google_query = db_barkod if db_barkod and db_barkod != "-" else db_ad
            google_markup = google_duymesi_duzelt(google_query)

            neticeler.append((caption, google_markup))


        if toplam_say > 10:
            neticeler.append((f"ℹ️ Cəmi {toplam_say} məhsul tapıldı. İlk 10-u göstərildi.\nDaha dəqiq axtarış üçün adı və ya barkodu tam daxil edin.", None))

        return neticeler
    except Exception as general_err:
        safe_print(f"❌ Axtarışda gözlənilməz xəta: {general_err}")
        return [("❌ Axtarış icra edilərkən xəta baş verdi. Xahiş olunur axtarışı yenidən cəhd edin.", None)]

# --- 3. BOT COMMAND HANDLERS ---
@tg_bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    txt = (message.text or "").strip()
    if "scanner" in txt:
        thread_id = getattr(message, 'message_thread_id', None)
        chat_id = message.chat.id
        u_name = urllib.parse.quote(message.from_user.first_name or "İstifadəçi")
        sep = "&" if "?" in SCANNER_URL else "?"
        scanner_url = f"{SCANNER_URL}{sep}chat_id={chat_id}&user_name={u_name}"
        if thread_id:
            scanner_url += f"&thread_id={thread_id}"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📷 Kameranı Aç və Skan Et", web_app=types.WebAppInfo(url=scanner_url)))
        safe_send_message(
            message.chat.id,
            "📷 **Barkod Skaneri Hazırdır!**\n\nAşağıdakı düyməyə toxunaraq kameranı açın və ya qalereyadan barkod şəkli seçin:",
            reply_markup=markup,
            thread_id=thread_id,
            reply_to_message_id=message.message_id
        )
        return

    metn = (
        "👋 **Salam! Dore Group Məhsul & Anbar Botuna Xoş Gəldiniz.**\n\n"
        "🔍 **Axtarış:** Məhsulun kodunu, adını, brendini və ya barkodun son 4 rəqəmini yazın.\n"
        "📷 **Skaner:** Aşağıdakı `📷 Barkod Skaneri` düyməsi ilə kameranı açıb barkodu dərhal oxuda bilərsiniz.\n"
        "📢 **Qrupa Elan:** Adminlər üçün rəsmi qrup bildirişi göndərmək imkanı.\n"
        "☎️ **Əlaqə:** Şirkətin məsul şöbələrinin əlaqə nömrələri.\n"
        "🧹 **Təmizlə:** `/temizle` və ya `temizle full` — çatı və köhnə axtarışları sıfırlamaq.\n"
        "📁 **Excel:** Yeni faylı bota göndərərək bazanı anında yeniləyə bilərsiniz (Admin şifrəsi ilə)."
    )
    try:
        thread_id = getattr(message, 'message_thread_id', None)
        is_priv = (message.chat.type == "private")
        safe_send_message(message.chat.id, metn, reply_markup=ana_menyu(is_priv), thread_id=thread_id, reply_to_message_id=message.message_id)
    except Exception as e:
        safe_print(f"❌ Welcome mesajı göndərmə xətası: {e}")

@tg_bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    """Kamera ilə skan edilmiş barkodu WebApp-dan qəbul edir və dərhal axtarış edir"""
    try:
        barcode = (message.web_app_data.data or "").strip()
        safe_print(f"📷 WebApp Kamera Skanı qəbul olundu: {barcode}")
        thread_id = getattr(message, 'message_thread_id', None)
        safe_send_message(message.chat.id, f"📷 **Skan edildi:** `{barcode}`\n🔍 Məlumat axtarılır...", thread_id=thread_id)

        neticeler = bazada_axtar(barcode)
        for res in neticeler:
            if isinstance(res, (tuple, list)):
                caption = str(res[0]) if len(res) > 0 else "ℹ️ Məlumat mövcuddur."
                inline_markup = res[1] if len(res) > 1 and isinstance(res[1], types.InlineKeyboardMarkup) else None
            else:
                caption = str(res)
                inline_markup = None
            safe_send_message(message.chat.id, caption, reply_markup=inline_markup, thread_id=thread_id)
    except Exception as e:
        safe_print(f"❌ WebApp data xətası: {e}")


@tg_bot.message_handler(commands=['temizle', 'clear', 'sil', 'clean'])
def handle_clear_chat(message):
    """Qrup adminləri üçün çatı və köhnə axtarışları təmizləyən əmr"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "İstifadəçi"
        chat_id = message.chat.id
        thread_id = getattr(message, 'message_thread_id', None)

        # 1. Qrup admini olub-olmadığını yoxlayırıq
        if not is_user_admin(message.chat, user_id):
            warn_msg = safe_send_message(
                chat_id,
                "⛔ **İcazə verilmədi!**\nÇatı və köhnə axtarışları təmizləmək hüququ yalnız qrup adminlərinə məxsusdur.",
                thread_id=thread_id,
                reply_to_message_id=message.message_id,
                track=False
            )
            if warn_msg and hasattr(warn_msg, 'message_id'):
                threading.Thread(target=auto_delete_message, args=(chat_id, warn_msg.message_id, 6), daemon=True).start()
            return

        # 2. Silinəcək mesaj sayını və 'full' rejimini müəyyənləşdiririk
        count = 50
        is_full = False
        parts = (message.text or "").lower().split()
        if any(p in parts for p in ["full", "tam", "hamisi", "0", "sıfırla", "sifirla"]):
            is_full = True
            count = 200  # Full rejimdə son 200 mesajı dərhal əhatə edir
        elif len(parts) > 1 and parts[1].isdigit():
            count = min(int(parts[1]), 200)

        safe_print(f"🧹 Çat təmizləmə başladı: Chat {chat_id}, Admin: {user_name} ({user_id}), Say: {count}, Full: {is_full}")

        # Silinəcək unikal mesaj ID-ləri
        ids_to_delete = set()

        # Bot tərəfindən göndərilmiş və izlənmiş bütün mesajlar
        for mid in CHAT_MESSAGES.get(chat_id, []):
            ids_to_delete.add(mid)
        CHAT_MESSAGES[chat_id] = []

        # Əmrin göndərildiyi cari mesaj
        ids_to_delete.add(message.message_id)

        # Əmrdən əvvəlki son 'count' sayda mesajı da əhatə edirik
        for offset in range(1, count + 1):
            ids_to_delete.add(message.message_id - offset)

        deleted_count = 0
        for mid in sorted(ids_to_delete, reverse=True):
            try:
                tg_bot.delete_message(chat_id, mid)
                deleted_count += 1
            except Exception:
                pass

        if is_full:
            # Baza keşini və axtarış yaddaşını da tam sıfırlayırıq
            DATA_CACHE["df"] = None
            DATA_CACHE["mtime"] = 0
            DATA_CACHE["filepath"] = None
            datani_yukle()

            info_text = (
                f"🧹 **ÇAT VƏ AXTARIŞLAR TAM SIFIRLANDI! (FULL RESET)** 0️⃣✨\n\n"
                f"👤 Admin: {user_name}\n"
                f"🗑️ Bütün köhnə axtarışlar və mesajlar silindi ({deleted_count} mesaj təmizləndi).\n"
                f"0️⃣ Axtarış bazası və yaddaş tam sıfırlandı!"
            )
        else:
            info_text = (
                f"🧹 **ÇAT TƏMİZLƏNDİ!** ✨\n\n"
                f"👤 Admin: {user_name}\n"
                f"🗑️ Köhnə axtarışlar və mesajlar silindi ({deleted_count} mesaj yoxlanıldı).\n"
                f"🔄 Axtarış tarixçəsi sıfırlandı!"
            )

        info_msg = safe_send_message(chat_id, info_text, thread_id=thread_id, track=False)

        # 5 saniyə sonra təsdiq bildirişi də avtomatik silinir və çat tərtəmiz qalır
        if info_msg and hasattr(info_msg, 'message_id'):
            threading.Thread(target=auto_delete_message, args=(chat_id, info_msg.message_id, 5), daemon=True).start()

    except Exception as e:
        safe_print(f"❌ Çat təmizləmə xətası: {e}")


def github_fayli_yenile(excel_fayl_yolu, user_name="Admin"):
    """
    Yeni qəbul olunmuş Excel faylını avtomatik olaraq GitHub reposuna göndərir (commit & push).
    Bu sayədə Render serveri avtomatik yenilənir və məlumatlar daimi saxlanılır.
    """
    if not excel_fayl_yolu or not os.path.exists(excel_fayl_yolu):
        return False, "Fayl tapılmadı"

    fayl_adi = os.path.basename(excel_fayl_yolu)
    repo_name = os.environ.get("GITHUB_REPO", "acolour2023-wq/Telegram_anbar")
    github_token = (
        GITHUB_TOKEN
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUBTOKEN")
        or os.environ.get("GH_TOKEN")
        or ""
    ).strip()
    commit_mesaji = f"🔄 Anbar Excel yeniləndi: {fayl_adi} ({user_name})"

    # 1. Üsul: GitHub REST API (Əgər GITHUB_TOKEN varsa - Render və serverlərdə ən etibarlı yol)
    if github_token:
        try:
            safe_print(f"🌐 GitHub API ilə fayl commit edilir: {repo_name}/{fayl_adi}...")
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            api_url = f"https://api.github.com/repos/{repo_name}/contents/{urllib.parse.quote(fayl_adi)}"

            sha = None
            r_get = requests.get(api_url, headers=headers, timeout=10)
            if r_get.status_code == 200:
                sha = r_get.json().get("sha")

            with open(excel_fayl_yolu, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "message": commit_mesaji,
                "content": content_b64,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha

            r_put = requests.put(api_url, headers=headers, json=payload, timeout=25)
            if r_put.status_code in [200, 201]:
                safe_print("✅ GitHub API ilə commit uğurlu oldu! Render yenilənməyə başladı.")
                return True, "GitHub API ilə push edildi"
            else:
                safe_print(f"⚠️ GitHub API cavabı: {r_put.status_code} - {r_put.text}")
        except Exception as api_err:
            safe_print(f"⚠️ GitHub API xətası: {api_err}")

    # 2. Üsul: Lokal Git əmrləri (Kompyuterdə işlədikdə)
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        safe_print("💻 Lokal Git ilə GitHub-a commit & push edilir...")
        subprocess.run(["git", "add", fayl_adi], cwd=current_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", commit_mesaji], cwd=current_dir, capture_output=True, text=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=current_dir, check=True, capture_output=True, text=True)
        safe_print("✅ Lokal Git ilə push tamamlandı.")
        return True, "Lokal Git ilə push edildi"
    except Exception as git_err:
        safe_print(f"ℹ️ Lokal Git push məlumatı: {git_err}")
        return False, str(git_err)

def execute_excel_update(file_id, file_name, chat_id, thread_id=None, user_name="İstifadəçi", reply_to_id=None):
    """Excel faylını təhlükəsiz yükləyir, yoxlayır və anbar bazasını yeniləyir"""
    try:
        status_msg = safe_send_message(
            chat_id, 
            "🔄 Yeni Excel faylı yüklənir və anbar bazası yoxlanılır, xahiş olunur gözləyin...", 
            thread_id=thread_id, 
            reply_to_message_id=reply_to_id
        )

        file_info = tg_bot.get_file(file_id)
        downloaded_file = tg_bot.download_file(file_info.file_path)

        target_path = fayli_tap()
        if not target_path:
            current_folder = os.path.dirname(os.path.abspath(__file__))
            target_path = os.path.join(current_folder, "Son_anbar_qaliqi.xlsx")

        # Təhlükəsizlik: Faylı birbaşa əzməzdən əvvəl temp fayla yazırıq və oxunmasını test edirik
        temp_path = target_path + ".tmp"
        with open(temp_path, 'wb') as f:
            f.write(downloaded_file)

        try:
            test_df = pd.read_excel(temp_path, dtype=str).fillna("")
            if len(test_df) == 0:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                safe_send_message(chat_id, "⚠️ Göndərilən Excel faylı boşdur! Yeniləmə ləğv edildi.", thread_id=thread_id)
                return
        except Exception as read_err:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            safe_send_message(chat_id, f"❌ Göndərilən fayl zədəlidir və ya düzgün Excel formatında deyil:\n{read_err}", thread_id=thread_id)
            return

        # Uğurlu oxunduqda ehtiyat (backup) çıxarırıq və köhnə faylı əvəzləyirik
        if os.path.exists(target_path):
            backup_path = target_path + ".bak"
            try:
                shutil.copyfile(target_path, backup_path)
            except Exception:
                pass
            os.remove(target_path)

        os.rename(temp_path, target_path)

        # Keşi sıfırlayırıq və yeni məlumatları oxuyuruq
        DATA_CACHE["df"] = None
        DATA_CACHE["mtime"] = 0
        DATA_CACHE["filepath"] = None

        df, err = datani_yukle()

        if err:
            safe_send_message(chat_id, f"❌ Fayl oxunarkən xəta baş verdi:\n{err}", thread_id=thread_id)
            return

        # Avtomatik GitHub-a göndəririk (Render-in daimi yenilənməsi üçün)
        git_ugurlu, git_mesaj = github_fayli_yenile(target_path, user_name)

        cavab = (
            f"✅ **YENİ EXCEL FAYLI QƏBUL OLUNDU!** 🎉\n\n"
            f"👤 Admin: {user_name}\n"
            f"📄 Fayl adı: {file_name}\n"
            f"📊 Ümumi sətir sayı: {len(df)} məhsul\n"
            f"⚡ Anbar bazası yeniləndi və dərhal istifadəyə hazırdır!"
        )

        if git_ugurlu:
            cavab += "\n\n🚀 **GitHub və Render serveri avtomatik yenilənməyə başladı!**"
        else:
            cavab += "\n\nℹ️ *(Lokal baza yeniləndi. Render 7/24 sinxronu üçün GITHUB_TOKEN əlavə edin)*"

        if status_msg and hasattr(status_msg, 'message_id'):
            try:
                tg_bot.edit_message_text(cavab, chat_id, status_msg.message_id)
                safe_print(f"📥 Yeni Excel uğurla tətbiq edildi ({user_name}): {file_name} ({len(df)} sətir)")
                return
            except Exception:
                pass

        safe_send_message(chat_id, cavab, thread_id=thread_id)
        safe_print(f"📥 Yeni Excel uğurla tətbiq edildi ({user_name}): {file_name} ({len(df)} sətir)")

    except Exception as e:
        safe_print(f"❌ Excel yükləmə xətası: {e}")
        safe_send_message(chat_id, f"❌ Fayl yüklənərkən xəta baş verdi: {e}", thread_id=thread_id)

@tg_bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        user_name = message.from_user.first_name or "İstifadəçi"
        user_id = message.from_user.id
        doc = message.document
        file_name = doc.file_name or ""
        thread_id = getattr(message, 'message_thread_id', None)
        
        if not (file_name.lower().endswith('.xlsx') or file_name.lower().endswith('.xls')):
            safe_send_message(message.chat.id, "⚠️ Xahiş olunur yalnız Excel (.xlsx / .xls) faylı göndərin.", thread_id=thread_id, reply_to_message_id=message.message_id)
            return

        # 1. Admin ID Yoxlanışı (Əgər ADMIN_IDS mühit dəyişəni təyin edilibsə)
        if ADMIN_IDS and user_id not in ADMIN_IDS:
            safe_print(f"⛔ İcazəsiz fayl yükləmə cəhdi: User ID {user_id} ({user_name})")
            safe_send_message(
                message.chat.id,
                f"⛔ **Giriş Qadağandır!**\n\nBu botda anbar bazasını yeniləmək hüququ yalnız təyin edilmiş adminlərə məxsusdur.\n🆔 Sizin Telegram ID: `{user_id}`",
                thread_id=thread_id,
                reply_to_message_id=message.message_id
            )
            return

        # 2. Şifrə birbaşa faylın izahatında (caption) yazılıbsa dərhal icra et
        caption = (message.caption or "").strip()
        if ADMIN_PASSWORD and caption and caption == ADMIN_PASSWORD:
            safe_print(f"🔑 Şifrə caption ilə təsdiqləndi: {user_name} ({user_id})")
            execute_excel_update(doc.file_id, file_name, message.chat.id, thread_id, user_name, message.message_id)
            return

        # 3. Əks halda şifrə gözləmə vəziyyətinə alırıq
        PENDING_UPLOADS[user_id] = {
            "file_id": doc.file_id,
            "file_name": file_name,
            "chat_id": message.chat.id,
            "thread_id": thread_id,
            "user_name": user_name,
            "attempts": 0,
            "timestamp": time.time()
        }

        safe_send_message(
            message.chat.id,
            f"🔐 **Admin Şifrəsi Tələb Olunur!**\n\n"
            f"📁 Fayl: `{file_name}`\n"
            f"Anbar bazasını yeniləmək üçün zəhmət olmasa **Xüsusi Admin Şifrəsini** daxil edin:\n\n"
            f"*(Əməliyyatı ləğv etmək üçün /cancel yazın)*",
            thread_id=thread_id,
            reply_to_message_id=message.message_id
        )

    except Exception as e:
        safe_print(f"❌ Document handler xətası: {e}")
        safe_send_message(message.chat.id, f"❌ Xəta baş verdi: {e}", thread_id=thread_id)

@tg_bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_name = message.from_user.first_name or "İstifadəçi"
        user_id = message.from_user.id
        txt = message.text.strip() if message.text else ""
        if not txt:
            return

        thread_id = getattr(message, 'message_thread_id', None)

        # 1. Gözləyən Admin Şifrəsi Yoxlanışı
        if user_id in PENDING_UPLOADS:
            pending = PENDING_UPLOADS[user_id]

            if txt.lower() in ["/cancel", "cancel", "imtina", "leqv", "ləğv"]:
                del PENDING_UPLOADS[user_id]
                safe_send_message(message.chat.id, "❌ Excel yeniləmə əməliyyatı ləğv edildi.", thread_id=thread_id, reply_to_message_id=message.message_id)
                return

            if txt == ADMIN_PASSWORD:
                file_id = pending["file_id"]
                file_name = pending["file_name"]
                del PENDING_UPLOADS[user_id]
                safe_print(f"🔑 Şifrə düzgün daxil edildi: {user_name} ({user_id})")
                execute_excel_update(file_id, file_name, message.chat.id, thread_id, user_name, message.message_id)
                return
            else:
                pending["attempts"] += 1
                if pending["attempts"] >= 3:
                    del PENDING_UPLOADS[user_id]
                    safe_print(f"⛔ 3 dəfə yanlış şifrə: {user_name} ({user_id})")
                    safe_send_message(message.chat.id, "⛔ 3 dəfə yanlış şifrə daxil edildi. Yeniləmə əməliyyatı ləğv edildi!", thread_id=thread_id, reply_to_message_id=message.message_id)
                else:
                    qalan = 3 - pending["attempts"]
                    safe_send_message(
                        message.chat.id, 
                        f"❌ Yanlış şifrə! (Qalan cəhd sayı: {qalan})\nZəhmət olmasa şifrəni yenidən yazın və ya ləğv etmək üçün /cancel yazın:", 
                        thread_id=thread_id, 
                        reply_to_message_id=message.message_id
                    )
                return

        # 2. Gözləyən Qrup Elanı Mətni
        if user_id in PENDING_ANNOUNCEMENTS:

            ann_info = PENDING_ANNOUNCEMENTS[user_id]
            del PENDING_ANNOUNCEMENTS[user_id]

            if txt.lower() in ["/cancel", "cancel", "imtina", "leqv", "ləğv"]:
                safe_send_message(message.chat.id, "❌ Qrup elanı göndərilməsi ləğv edildi.", thread_id=thread_id, reply_to_message_id=message.message_id)
                return

            now_str = time.strftime("%d.%m.%Y %H:%M")
            elan_metn = (
                "📢 **DORE GROUP MMC — RƏSMİ BİLDİRİŞ** ⚠️\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{txt}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Elan verən:** {user_name}\n"
                f"🕒 **Tarix:** {now_str}"
            )
            target_chat_id = ann_info.get("chat_id", message.chat.id)
            target_thread_id = ann_info.get("thread_id")
            sent_msg = safe_send_message(target_chat_id, elan_metn, thread_id=target_thread_id)
            try:
                if sent_msg and hasattr(sent_msg, 'message_id') and message.chat.type in ['group', 'supergroup']:
                    tg_bot.pin_chat_message(target_chat_id, sent_msg.message_id)
            except Exception:
                pass

            if target_chat_id != message.chat.id:
                safe_send_message(message.chat.id, "✅ Elan qrupa uğurla göndərildi!", thread_id=thread_id, reply_to_message_id=message.message_id)
            return

        # Gələn mesajın ID-sini izləyirik
        CHAT_MESSAGES.setdefault(message.chat.id, []).append(message.message_id)

        # Qrupdan mesaj gələrsə avtomatik hədəf qrup kimi qeyd edirik
        if message.chat.type in ['group', 'supergroup']:
            global GROUP_CHAT_ID
            GROUP_CHAT_ID = str(message.chat.id)

        txt_low = txt.lower()

        # Səhər salamlama mesajını test etmək üçün əmr
        if txt_low in ["/seher", "/sabah", "/salamlama"]:
            test_greeting = (
                "🌅 **Sabahınız xeyir, Dore Group MMC komandası!** ☀️\n\n"
                "💼 Hər birinizə uğurlu, bərəkətli və bol enerjili iş günü arzulayırıq! 🚀\n\n"
                "📦 *Anbar botu aktivdir — məhsul qalığını və qiymətini öyrənmək üçün barkodun son 4 rəqəmini və ya adını yazmağınız kifayətdir.*"
            )
            safe_send_message(message.chat.id, test_greeting, thread_id=thread_id)
            return

        if any(txt_low.startswith(cmd) for cmd in ["/temizle", "temizle", "/clear", "clear", "/sil", "sil", "🧹 çatı təmizlə", "çatı təmizlə", "chati temizle"]):
            handle_clear_chat(message)
            return

        is_priv = (message.chat.type == "private")

        if txt in ["☎️ Əlaqə & Şöbələr", "əlaqə", "elaqe", "/elaqe", "/kontakt"]:
            safe_send_message(message.chat.id, CONTACTS_INFO, reply_markup=ana_menyu(is_priv), thread_id=thread_id, reply_to_message_id=message.message_id)
            return

        if txt in ["📢 Qrupa Elan", "qrupa elan", "/elan"]:
            if not is_user_admin(message.chat, user_id):
                warn_msg = safe_send_message(
                    message.chat.id,
                    "⛔ **İcazə verilmədi!**\nQrupa rəsmi elan göndərmək hüququ yalnız adminlərə məxsusdur.",
                    thread_id=thread_id,
                    reply_to_message_id=message.message_id,
                    track=False
                )
                if warn_msg and hasattr(warn_msg, 'message_id'):
                    threading.Thread(target=auto_delete_message, args=(message.chat.id, warn_msg.message_id, 6), daemon=True).start()
                return

            PENDING_ANNOUNCEMENTS[user_id] = {
                "chat_id": message.chat.id,
                "thread_id": thread_id
            }
            safe_send_message(
                message.chat.id,
                "📢 **Rəsmi Qrup Elanı Rejimi**\n\n"
                "Zəhmət olmasa qrupa göndəriləcək elan mətnini yazın:\n\n"
                "*(Ləğv etmək üçün /cancel yazın)*",
                thread_id=thread_id,
                reply_to_message_id=message.message_id
            )
            return

        if txt in ["📷 Barkod Skaneri", "barkod skaneri", "/skaner", "/scanner", "skaner", "scanner"]:
            chat_id = message.chat.id
            u_name = urllib.parse.quote(message.from_user.first_name or "İstifadəçi")
            sep = "&" if "?" in SCANNER_URL else "?"
            scanner_url = f"{SCANNER_URL}{sep}chat_id={chat_id}&user_name={u_name}"
            if thread_id:
                scanner_url += f"&thread_id={thread_id}"

            markup = types.InlineKeyboardMarkup(row_width=1)
            if is_priv:
                btn_cam = types.InlineKeyboardButton("📷 Kameranı Aç və Skan Et", web_app=types.WebAppInfo(url=scanner_url))
            else:
                btn_cam = types.InlineKeyboardButton("📷 Kameranı Aç və Skan Et", url=scanner_url)

            btn_bot = types.InlineKeyboardButton("💬 Şəxsi Çatda Skaner Aç", url="https://t.me/Anbarbotu_bot?start=scanner")
            markup.add(btn_cam, btn_bot)
            safe_send_message(
                message.chat.id,
                "📷 **Dore Group — Barkod Skaneri**\n\n"
                "Aşağıdakı düyməyə toxunaraq kameranızı açın və ya barkod şəklini seçin.\n"
                "Tapılan məhsul məlumatı avtomatik olaraq bu çata göndəriləcək:",
                reply_markup=markup,
                thread_id=thread_id,
                reply_to_message_id=message.message_id
            )
            return

        if txt == "📦 Anbar & Qiymət":
            cavab = "🔍 Axtarmaq istədiyiniz məhsulun kodunu, adını, brendini və ya barkodunu daxil edin:"
            safe_send_message(message.chat.id, cavab, reply_markup=ana_menyu(is_priv), thread_id=thread_id, reply_to_message_id=message.message_id)
            return



        if txt == "🗑 Yaddaşı Təmizlə":
            DATA_CACHE["df"] = None
            DATA_CACHE["mtime"] = 0
            DATA_CACHE["filepath"] = None
            df, err = datani_yukle()
            if err:
                safe_send_message(message.chat.id, err, reply_markup=ana_menyu(), thread_id=thread_id)
            else:
                safe_send_message(message.chat.id, f"🗑 Yaddaş (Keş) təmizləndi!\n🔄 Excel faylı təkrar oxundu: {len(df)} sətir yükləndi.", reply_markup=ana_menyu(), thread_id=thread_id)
            return

        # Təkrar axtarış bildirişi (az əvvəl başqası da axtarıbsa)
        query_key = f"{message.chat.id}:{az_normalize(txt)}"
        now_ts = time.time()
        repeat_note = ""
        prev_search = RECENT_QUERIES.get(query_key)
        if prev_search and (now_ts - prev_search.get("time", 0) < 120) and prev_search.get("user_id") != user_id:
            sec_ago = max(1, int(now_ts - prev_search["time"]))
            prev_u = prev_search.get("user_name", "başqa istifadəçi")
            repeat_note = f"💡 *(Qeyd: Bu məhsul {sec_ago} san əvvəl {prev_u} tərəfindən də soruşulmuşdu)*\n"
        RECENT_QUERIES[query_key] = {"user_name": user_name, "user_id": user_id, "time": now_ts}

        neticeler = bazada_axtar(txt)

        # Məhsul tapılmadı və ya xəta halı
        if not neticeler or (len(neticeler) == 1 and ("tapılmadı" in str(neticeler[0][0]) or "xəta" in str(neticeler[0][0]).lower())):
            fail_text = f"👤 **Sorğu:** {user_name}\n🔍 **Axtarılan:** `{txt}`\n━━━━━━━━━━━━━━━━━━━━\n" + str(neticeler[0][0])
            safe_send_message(message.chat.id, fail_text, thread_id=thread_id, reply_to_message_id=message.message_id)
            return

        # Yalnız real məhsul kartlarını seçirik (sonuncu "Cəmi X məhsul tapıldı" info sətiri istisna olmaqla)
        product_results = [r for r in neticeler if isinstance(r, (tuple, list)) and len(r) > 1 and r[1] is not None]
        if not product_results:
            product_results = neticeler

        total_prods = len(product_results)

        # 1 məhsul tapıldıqda tək kart göndəririk
        if total_prods == 1:
            caption = str(product_results[0][0])
            header = f"👤 **Sorğu:** {user_name} | 🔍 **Axtarılan:** `{txt}`\n{repeat_note}━━━━━━━━━━━━━━━━━━━━\n"
            full_caption = header + caption
            inline_markup = product_results[0][1] if len(product_results[0]) > 1 else None
            safe_send_message(message.chat.id, full_caption, reply_markup=inline_markup, thread_id=thread_id, reply_to_message_id=message.message_id)
            return

        # 1-dən çox məhsul tapıldıqda: İnteraktiv Vərəqləmə (Pagination)
        session_id = f"{user_id}_{int(time.time()*1000) % 1000000}"

        if len(SEARCH_SESSIONS) > 500:
            old_keys = [k for k, v in SEARCH_SESSIONS.items() if now_ts - v.get("time", 0) > 1800]
            for k in old_keys:
                SEARCH_SESSIONS.pop(k, None)

        SEARCH_SESSIONS[session_id] = {
            "user_name": user_name,
            "user_id": user_id,
            "query": txt,
            "results": product_results,
            "time": now_ts
        }

        first_caption = str(product_results[0][0])
        header = (
            f"👤 **Sorğu:** {user_name} | 🔍 **Axtarılan:** `{txt}`\n"
            f"{repeat_note}"
            f"📊 **Məhsul:** 1 / {total_prods} *(Cəmi {total_prods} uyğun məhsul tapıldı)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        full_caption = header + first_caption
        p_markup = build_pagination_markup(session_id, 0, total_prods, product_results[0][1])

        safe_send_message(message.chat.id, full_caption, reply_markup=p_markup, thread_id=thread_id, reply_to_message_id=message.message_id)

    except Exception as e:
        safe_print(f"❌ Göndərmə xətası: {e}")


@tg_bot.callback_query_handler(func=lambda call: call.data and call.data.startswith('nav:'))
def handle_pagination_callback(call):
    """Məhsulları çatda yerindəcə vərəqləmək (Pagination) üçün callback işləyicisi"""
    try:
        parts = call.data.split(':')
        if len(parts) != 3:
            tg_bot.answer_callback_query(call.id)
            return

        session_id = parts[1]
        target_idx = int(parts[2])

        session = SEARCH_SESSIONS.get(session_id)
        if not session:
            tg_bot.answer_callback_query(call.id, "ℹ️ Axtarış sessiyasının vaxtı bitib. Xahiş olunur yenidən axtarın.", show_alert=False)
            return

        results = session["results"]
        total = len(results)
        if total == 0:
            tg_bot.answer_callback_query(call.id)
            return

        target_idx = target_idx % total
        user_name = session["user_name"]
        query_txt = session["query"]

        caption_raw = str(results[target_idx][0])
        header = (
            f"👤 **Sorğu:** {user_name} | 🔍 **Axtarılan:** `{query_txt}`\n"
            f"📊 **Məhsul:** {target_idx + 1} / {total} *(Cəmi {total} uyğun məhsul tapıldı)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        full_caption = header + caption_raw

        google_markup = results[target_idx][1] if len(results[target_idx]) > 1 else None
        markup = build_pagination_markup(session_id, target_idx, total, google_markup)

        try:
            tg_bot.edit_message_text(
                full_caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            tg_bot.edit_message_text(
                full_caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )

        tg_bot.answer_callback_query(call.id)
    except Exception as e:
        safe_print(f"⚠️ Pagination callback xətası: {e}")
        try:
            tg_bot.answer_callback_query(call.id)
        except Exception:
            pass

@tg_bot.callback_query_handler(func=lambda call: call.data == 'nav_noop')
def handle_nav_noop(call):
    """Səhifə sayğacı düyməsinə toxunulduqda sakitcə təsdiqləyir"""
    try:
        tg_bot.answer_callback_query(call.id)
    except Exception:
        pass


def start_bot():
    safe_print("🚀 BOT BAŞLADILDI (7/24 Rejim - @Anbarbotu_bot)...")
    try:
        tg_bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        safe_print(f"⚠️ Webhook təmizləmə: {e}")

    # Səhər salamlama və motivasiya mesajı taymerini başladırıq
    try:
        greeting_t = threading.Thread(target=morning_greeting_worker, daemon=True)
        greeting_t.start()
    except Exception as ge:
        safe_print(f"⚠️ Səhər salamlama taymeri başladıla bilmədi: {ge}")

    while True:
        try:
            tg_bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            safe_print(f"❌ Bot polling xətası (5 saniyə sonra yenidən cəhd edilir): {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()



