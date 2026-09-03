import os
import glob
import sys
import unicodedata
import urllib.parse
import time
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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8273382721:AAGh_3EKl5VLdcKttnh6HEeobdYsZnRiFBw")
tg_bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Admin və Təhlükəsizlik Ayarları
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "anbar2026")
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# GitHub Avtomatik Sinxronizasiya (Render üçün)
GITHUB_REPO = os.environ.get("GITHUB_REPO", "acolour2023-wq/Telegram_anbar")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# Təsdiq gözləyən fayl yeniləmələri (user_id -> info)
PENDING_UPLOADS = {}

# Təsdiq gözləyən qrup elanları (user_id -> info)
PENDING_ANNOUNCEMENTS = {}

# Çatda göndərilən və izlənən mesaj ID-ləri (chat_id -> [message_id, ...])
CHAT_MESSAGES = {}

# Barkod Kamera Skaneri WebApp URL (Render üzərindən)
SCANNER_URL = os.environ.get("SCANNER_URL", "https://telegram-anbar-11y6.onrender.com/scanner")

# Dore Group MMC - Əlaqə və Şöbələr Məlumatı
CONTACTS_INFO = (
    "🏢 **DORE GROUP MMC — ƏLAQƏ VƏ ŞÖBƏLƏR** 📞\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📦 **Anbar Müdiri / Təhvil-Təslim:**\n"
    "📞 `+994 50 200 10 20` *(Zəng üçün toxunun)*\n\n"
    "🧾 **Mühasibatlıq / Faktura & Qaimə:**\n"
    "📞 `+994 55 300 40 50`\n\n"
    "🚚 **Logistika & Sifarişlərin Çatdırılması:**\n"
    "📞 `+994 70 500 60 70`\n\n"
    "💼 **Baş Satış Meneceri:**\n"
    "📞 `+994 51 700 80 90`\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📍 **Ünvan:** Bakı şəhəri, Baş Anbar\n"
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
                if barkod_norm == query_norm or kod_norm == query_norm:
                    score = 100
                elif barkod_norm.endswith(query_norm) or kod_norm.endswith(query_norm):
                    score = 80
                elif query_norm in barkod_norm or query_norm in kod_norm:
                    score = 60
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
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
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
        if caption == ADMIN_PASSWORD:
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

        txt_low = txt.lower()
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

        if txt in ["📷 Barkod Skaneri", "barkod skaneri", "/skaner", "/scanner"]:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📷 Kameranı Aç və Skan Et", web_app=types.WebAppInfo(url=SCANNER_URL)))
            safe_send_message(
                message.chat.id,
                "📷 **Kamera ilə Barkod Skaneri**\n\n"
                "Aşağıdakı düyməyə toxunaraq telefonunuzun kamerasını açın və məhsulun barkodunu skan edin:",
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

        neticeler = bazada_axtar(txt)

        for res in neticeler:
            if isinstance(res, (tuple, list)):
                caption = str(res[0]) if len(res) > 0 else "ℹ️ Məlumat mövcuddur."
                inline_markup = res[1] if len(res) > 1 and isinstance(res[1], types.InlineKeyboardMarkup) else None
            else:
                caption = str(res)
                inline_markup = None

            safe_send_message(message.chat.id, caption, reply_markup=inline_markup, thread_id=thread_id)

    except Exception as e:
        safe_print(f"❌ Göndərmə xətası: {e}")


def start_bot():
    safe_print("🚀 BOT BAŞLADILDI (7/24 Rejim - @Anbarbotu_bot)...")
    try:
        tg_bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        safe_print(f"⚠️ Webhook təmizləmə: {e}")

    while True:
        try:
            tg_bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            safe_print(f"❌ Bot polling xətası (5 saniyə sonra yenidən cəhd edilir): {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()



