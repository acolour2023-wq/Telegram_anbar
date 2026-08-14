# 🤖 Telegram Anbar Botu (7/24 Render & GitHub)

Bu layihə Excel faylından məhsul, qiymət, brend, barkod və anbar qalıqlarını Telegram üzərindən axtarmaq üçün 7/24 işləyən avtomatik bot sistemidir.

## 🚀 Xüsusiyyətlər
- ⚡ **7/24 Kesintisiz İşləmə**: Flask Veb Server + Telegram Bot background thread.
- 📦 **Excel RAM Caching**: Excel faylı yaddaşda saxlanılır və axtarışlar anlıq cavablandırılır.
- 🖼️ **Google Şəkillər Düyməsi**: Axtarılan məhsulun şəklini Google-da açmaq üçün inline button.
- 🛡️ **Avto-Bərpa**: İnternet və ya Telegram serverində qopma olduqda avtomatik təkrar qoşulma (`while True` retry loop).

---

## 🛠️ GitHub-a Yükləmək Üçün Command-lar

```bash
git remote add origin https://github.com/ISTIFADECI_ADI/telegram_excel_bot.git
git push -u origin main
```

---

## 🌐 Render-də 7/24 Deploy Etmək

1. [Render Dashboard](https://dashboard.render.com/)-a daxil olun.
2. **New +** düyməsini sıxıb **Web Service** seçin.
3. GitHub repozitoriyanızı seçin.
4. Tənzimləmələr:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Environment Variables**:
     - `TELEGRAM_TOKEN` = `8273382721:AAGh_3EKl5VLdcKttnh6HEeobdYsZnRiFBw`
5. **Create Web Service** düyməsini sıxın.

---

## ⏰ Render Free Tier-i 7/24 Oyaq Saxlamaq (UptimeRobot)

Render-in pulsuz planı 15 dəqiqə sorğu gəlmədikdə serveri yuxuya verir. Botun 7/24 aktiv qalması üçün:
1. [UptimeRobot.com](https://uptimerobot.com/)-da pulsuz hesab açın.
2. **Add New Monitor** seçin:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Anbar Bot Ping`
   - **URL**: `https://SENIN-APP-ADIN.onrender.com/health`
   - **Monitoring Interval**: `5 minutes`
3. Saxlayın! Artıq Render serveriniz 7/24 heç vaxt sönməyəcək.
