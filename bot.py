import os
import glob
import sys
import unicodedata
import urllib.parse
import time
import re
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

# --- 1. AYARLAR ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8273382721:AAGh_3EKl5VLdcKttnh6HEeobdYsZnRiFBw")
tg_bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Keş (Cache) mexanizmi: Excel faylını RAM-da saxlamaq üçün
DATA_CACHE = {
    "df": None,
    "mtime": 0,
    "filepath": None
}

# --- 2. KÖMƏKÇİ FUNKSİYALAR ---
def mehsul_sekli_tap(axtaris_metni):
    """Məhsul adından birbaşa dəqiq şəkil linkini tapan köməkçi funksiya"""
    if not axtaris_metni or axtaris_metni == "-":
        return None
    try:
        temiz_metn = re.sub(r'\(.*?\)', '', axtaris_metni).strip()
        temiz_metn = ' '.join(temiz_metn.split())

        url = f"https://www.bing.com/images/async?q={urllib.parse.quote(temiz_metn)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=2.5)
        thumbs = re.findall(r'https?://tse[0-9]\.mm\.bing\.net/th/id/OIP\.[^"\'\s\\?&]+', r.text)
        if thumbs:
            return thumbs[0]
        thumbs2 = re.findall(r'https?://[a-z0-9]+\.bing\.net/th\?id=OIP\.[^"\'\s\\&]+', r.text)
        if thumbs2:
            return thumbs2[0]
        murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+\.(?:jpg|jpeg|png|webp))', r.text, re.IGNORECASE)
        if murls:
            return murls[0]
    except Exception:
        pass
    return None

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

    mtime = os.path.getmtime(fayl)
    
    if DATA_CACHE["df"] is not None and DATA_CACHE["mtime"] == mtime and DATA_CACHE["filepath"] == fayl:
        return DATA_CACHE["df"], None

    try:
        df = pd.read_excel(fayl, dtype=str).fillna("")
        DATA_CACHE["df"] = df
        DATA_CACHE["mtime"] = mtime
        DATA_CACHE["filepath"] = fayl
        safe_print(f"🔄 Excel yaddaşa yükləndi: {os.path.basename(fayl)} ({len(df)} sətir)")
        return df, None
    except Exception as e:
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

def ana_menyu():
    """Botun əsas düymələr menyusu"""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_anbar = types.KeyboardButton("📦 Anbar & Qiymət")
    btn_yaddas = types.KeyboardButton("🗑 Yaddaşı Təmizlə")
    markup.add(btn_anbar, btn_yaddas)
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

    kod_col = next((orig for orig, clean in col_map.items() if 'kod' in clean or 'code' in clean), None)
    ad_col = next((orig for orig, clean in col_map.items() if 'ad' in clean or 'name' in clean), None)
    qiymet_col = next((orig for orig, clean in col_map.items() if 'qiym' in clean or 'qym' in clean or 'price' in clean), None)
    barkod_col = next((orig for orig, clean in col_map.items() if 'barkod' in clean or 'barcode' in clean), None)
    brend_col = next((orig for orig, clean in col_map.items() if 'brend' in clean or 'brand' in clean), None)
    qalig_col = next((orig for orig, clean in col_map.items() if 'qalig' in clean or 'qaliq' in clean or 'stok' in clean or 'say' in clean), None)

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
            qiymet = f"{qiymet_val:.2f}".rstrip('0').rstrip('.')
        except Exception:
            qiymet = qiymet_raw

        goster_brend = db_brend if db_brend and db_brend.lower() != "nan" else "-"
        goster_barkod = db_barkod if db_barkod and db_barkod.lower() != "nan" else "-"
        goster_qalig = db_qalig if db_qalig and db_qalig.lower() != "nan" else "-"

        caption = (
            f"🆔 Kod: {db_kod}\n"
            f"📦 Məhsul: {db_ad}\n"
            f"🏷️ Brend: {goster_brend}\n"
            f"🏷️ Qiymət: {qiymet} AZN\n"
            f"📊 Barkod: {goster_barkod}"
        )
        if qalig_col and goster_qalig != "-":
            caption += f"\n📊 Qalıq: {goster_qalig}"

        google_query = db_barkod if db_barkod and db_barkod != "-" else db_ad
        google_markup = google_duymesi_duzelt(google_query)

        neticeler.append((caption, google_markup))

    if toplam_say > 10:
        neticeler.append((f"ℹ️ Cəmi {toplam_say} məhsul tapıldı. İlk 10-u göstərildi.\nDaha dəqiq axtarış üçün adı və ya barkodu tam daxil edin.", None))

    return neticeler

# --- 3. BOT COMMAND HANDLERS ---
@tg_bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    metn = (
        "👋 Salam! Məhsul axtarış botuna xoş gəldiniz.\n\n"
        "🔍 Axtarmaq istədiyiniz məhsulun kodunu, adını, brendini və ya barkodunu (son 4 rəqəmini) yazın.\n"
        "📁 Yeni Excel faylını bota göndərərək anbarı anında yeniləyə bilərsiniz.\n\n"
        "Aşağıdakı menyu düymələrindən istifadə edə bilərsiniz:"
    )
    try:
        tg_bot.reply_to(message, metn, reply_markup=ana_menyu())
    except Exception as e:
        safe_print(f"❌ Welcome mesajı göndərmə xətası: {e}")

@tg_bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        user_name = message.from_user.first_name or "İstifadəçi"
        doc = message.document
        file_name = doc.file_name or ""
        
        if not (file_name.lower().endswith('.xlsx') or file_name.lower().endswith('.xls')):
            tg_bot.reply_to(message, "⚠️ Xahiş olunur yalnız Excel (.xlsx / .xls) faylı göndərin.")
            return

        status_msg = tg_bot.reply_to(message, "🔄 Yeni Excel faylı yüklənir və anbar yenilənir, xahiş olunur gözləyin...")

        file_info = tg_bot.get_file(doc.file_id)
        downloaded_file = tg_bot.download_file(file_info.file_path)

        target_path = fayli_tap()
        if not target_path:
            current_folder = os.path.dirname(os.path.abspath(__file__))
            target_path = os.path.join(current_folder, "Son_anbar_qaliqi.xlsx")

        with open(target_path, 'wb') as f:
            f.write(downloaded_file)

        DATA_CACHE["df"] = None
        DATA_CACHE["mtime"] = 0
        DATA_CACHE["filepath"] = None

        df, err = datani_yukle()

        if err:
            tg_bot.edit_message_text(f"❌ Fayl oxunarkən xəta baş verdi:\n{err}", message.chat.id, status_msg.message_id)
        else:
            cavab = (
                f"✅ YENİ EXCEL FAYLI QƏBUL OLUNDU! 🎉\n\n"
                f"📄 Fayl adı: {file_name}\n"
                f"📊 Ümumi sətir sayısı: {len(df)} məhsul\n"
                f"⚡ Anbar 1 saniyəyə yeniləndi və dərhal istifadəyə hazırdır!"
            )
            tg_bot.edit_message_text(cavab, message.chat.id, status_msg.message_id)
            safe_print(f"📥 Yeni Excel yükləndi ({user_name}): {file_name} ({len(df)} sətir)")

    except Exception as e:
        safe_print(f"❌ Excel yükləmə xətası: {e}")
        tg_bot.reply_to(message, f"❌ Fayl yüklənərkən xəta baş verdi: {e}")

@tg_bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_name = message.from_user.first_name or "İstifadəçi"
        txt = message.text.strip() if message.text else ""
        if not txt:
            return

        safe_print(f"📩 Mesaj ({user_name}): {txt}")
        thread_id = getattr(message, 'message_thread_id', None)

        if txt == "📦 Anbar & Qiymət":
            cavab = "🔍 Axtarmaq istədiyiniz məhsulun kodunu, adını, brendini və ya barkodunu daxil edin:"
            tg_bot.reply_to(message, cavab, reply_markup=ana_menyu())
            return

        if txt == "🗑 Yaddaşı Təmizlə":
            DATA_CACHE["df"] = None
            DATA_CACHE["mtime"] = 0
            DATA_CACHE["filepath"] = None
            df, err = datani_yukle()
            if err:
                tg_bot.reply_to(message, err, reply_markup=ana_menyu())
            else:
                tg_bot.reply_to(message, f"🗑 Yaddaş (Keş) təmizləndi!\n🔄 Excel faylı təkrar oxundu: {len(df)} sətir yükləndi.", reply_markup=ana_menyu())
            return

        neticeler = bazada_axtar(txt)

        for res in neticeler:
            if isinstance(res, (tuple, list)):
                caption = res[0]
                inline_markup = res[1] if len(res) > 1 else None
            else:
                caption = str(res)
                inline_markup = None

            if inline_markup:
                tg_bot.send_message(message.chat.id, caption, reply_markup=inline_markup, message_thread_id=thread_id)
            else:
                tg_bot.send_message(message.chat.id, caption, message_thread_id=thread_id)

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


