import os
import glob
import sys
import unicodedata
import urllib.parse
import time
import pandas as pd
import telebot
from telebot import types

# Windows konsolunda UTF-8 və emoji dəstəyini təmin edirik
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
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
def sutun_temizle(c):
    """Sütun adlarını kiçik hərflərə çevirir və Unicode bələdçi simvollarını (\u0307 kimi) təmizləyir."""
    s = str(c).lower().strip()
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if unicodedata.category(ch) != 'Mn')

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
    Bu keç mexanizmi axtarış sürətini ciddi şəkildə artırır.
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
        print(f"🔄 Excel yaddaşa yükləndi: {os.path.basename(fayl)} ({len(df)} sətir)")
        return df, None
    except Exception as e:
        return None, f"❌ Fayl oxunarkən xəta baş verdi: {e}"

def temizle(deyer):
    """Məlumatları təmizləyir və '.0' / ',00' sonluqlarını təhlükəsiz şəkildə silir."""
    if pd.isna(deyer):
        return ""
    s = str(deyer).strip()
    if s.lower() in ["nan", "none"]:
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
    # &tbm=isch parametrini əlavə edirik ki, birbaşa Google "Şəkillər" (Images/Картинки) tabı açılsın
    url = f"https://www.google.com/search?q={encoded_text}&tbm=isch"
    btn = types.InlineKeyboardButton("🖼️ Şəklə Bax (Google)", url=url)
    markup.add(btn)
    return markup

def bazada_axtar(axtaris_cumlesi):
    df, err = datani_yukle()
    if err:
        return [(err, None)]

    axtarilan_sozler = str(axtaris_cumlesi).lower().split()
    if not axtarilan_sozler:
        return [("ℹ️ Xahiş olunur axtarış sözü daxil edin.", None)]

    print(f"🔎 Axtarılır: {axtarilan_sozler}")

    col_map = {c: sutun_temizle(c) for c in df.columns}

    kod_col = next((orig for orig, clean in col_map.items() if 'kod' in clean or 'code' in clean), None)
    ad_col = next((orig for orig, clean in col_map.items() if 'ad' in clean or 'name' in clean), None)
    qiymet_col = next((orig for orig, clean in col_map.items() if 'qiym' in clean or 'qym' in clean or 'price' in clean), None)
    barkod_col = next((orig for orig, clean in col_map.items() if 'barkod' in clean or 'barcode' in clean), None)
    brend_col = next((orig for orig, clean in col_map.items() if 'brend' in clean or 'brand' in clean), None)
    qalig_col = next((orig for orig, clean in col_map.items() if 'qalig' in clean or 'qaliq' in clean or 'stok' in clean or 'say' in clean), None)

    if not kod_col and not ad_col: 
        return [("❌ Excel faylında uyğun sütunlar ('KODU', 'ADI') tapılmadı.", None)]

    neticeler = []
    records = df.to_dict('records')

    for row in records:
        db_kod = temizle(row.get(kod_col, "")) if kod_col else ""
        db_ad = str(row.get(ad_col, "")).strip() if ad_col else ""
        db_barkod = temizle(row.get(barkod_col, "")) if barkod_col else ""
        db_brend = str(row.get(brend_col, "")).strip() if brend_col else ""
        db_qalig = temizle(row.get(qalig_col, "")) if qalig_col else ""

        tam_setir = f"{db_kod} {db_barkod} {db_ad} {db_brend}".lower()

        if all(soz in tam_setir for soz in axtarilan_sozler):
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
                f"🏷 Məhsul: {db_ad}\n"
                f"🏢 Brend: {goster_brend}\n"
                f"💰 Qiymət: {qiymet} AZN\n"
                f"🔢 Barkod: {goster_barkod}"
            )
            if qalig_col and goster_qalig != "-":
                caption += f"\n📈 Qalıq: {goster_qalig}"

            # Google Şəkillər axtarışı üçün düymə
            google_query = db_barkod if db_barkod and db_barkod != "-" else db_ad
            google_markup = google_duymesi_duzelt(google_query)

            neticeler.append((caption, google_markup))

            if len(neticeler) >= 10:
                break

    if not neticeler:
        return [("❌ Uyğun məhsul tapılmadı.", None)]

    return neticeler

# --- 3. BOT COMMAND HANDLERS ---
@tg_bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    metn = (
        "👋 Salam! Məhsul axtarış botuna xoş gəldiniz.\n\n"
        "🔍 Axtarmaq istədiyiniz məhsulun kodunu, adını, brendini və ya barkodunu yazın.\n"
        "Aşağıdakı menyu düymələrindən istifadə edə bilərsiniz:"
    )
    try:
        tg_bot.reply_to(message, metn, reply_markup=ana_menyu())
    except Exception as e:
        print(f"❌ Welcome mesajı göndərmə xətası: {e}")

@tg_bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_name = message.from_user.first_name or "İstifadəçi"
        txt = message.text.strip()
        print(f"📩 Mesaj ({user_name}): {txt}")

        # Menyu düymələri
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

        # Ümumi axtarış
        neticeler = bazada_axtar(txt)

        for caption, inline_markup in neticeler:
            if inline_markup:
                tg_bot.send_message(message.chat.id, caption, reply_markup=inline_markup)
            else:
                tg_bot.send_message(message.chat.id, caption)

    except Exception as e:
        print(f"❌ Göndərmə xətası: {e}")

def start_bot():
    print("🚀 BOT BAŞLADILDI (7/24 Rejim - @Anbarbotu_bot)...")
    while True:
        try:
            try:
                tg_bot.delete_webhook(drop_pending_updates=True)
            except Exception as e:
                print(f"⚠️ Webhook təmizləmə: {e}")
            tg_bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            print(f"❌ Bot polling xətası (5 saniyə sonra yenidən cəhd edilir): {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
