import os
import threading
import time
import socket
from flask import Flask, render_template_string, jsonify, request
import bot

def acquire_bot_lock():
    """Çoxlu Gunicorn worker-ləri olduqda eyni botun bir neçə dəfə işə düşməsinin (409 Conflict) qarşısını alır"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 47200))
        return s
    except Exception:
        return None

lock_socket = acquire_bot_lock()
if lock_socket is not None:
    bot.safe_print("🔒 Bot kilidi alındı. Telegram bot thread-i başladılır...")
    bot_thread = threading.Thread(target=bot.start_bot, daemon=True)
    bot_thread.start()
else:
    bot.safe_print("⚠️ Bot artıq başqa prosesdə çalışır (409 Conflict-in qarşısı alındı).")


app = Flask(__name__)
start_time = time.time()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Anbar Botu - 7/24 Status</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px;
            max-width: 550px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            text-align: center;
        }
        .badge-status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            border: 1px solid rgba(74, 222, 128, 0.3);
            padding: 8px 16px;
            border-radius: 9999px;
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 20px;
        }
        .pulse {
            width: 10px;
            height: 10px;
            background-color: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
        h1 { font-size: 2rem; margin-bottom: 10px; font-weight: 700; color: #ffffff; }
        p.subtitle { color: #94a3b8; font-size: 1rem; margin-bottom: 30px; }
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 30px;
            text-align: left;
        }
        .info-card {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 16px;
            border-radius: 16px;
        }
        .info-card span.label { display: block; color: #64748b; font-size: 0.8rem; margin-bottom: 4px; }
        .info-card span.val { font-size: 1.1rem; font-weight: 600; color: #e2e8f0; }
        .btn-link {
            display: inline-block;
            width: 100%;
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: #ffffff;
            font-weight: 600;
            padding: 14px;
            border-radius: 12px;
            text-decoration: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
        }
        .btn-link:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        }
        .footer-note {
            margin-top: 25px;
            font-size: 0.85rem;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="badge-status">
            <div class="pulse"></div>
            <span>Bot Aktivdir (7/24 Server)</span>
        </div>
        <h1>Telegram Anbar Botu</h1>
        <p class="subtitle">Render / GitHub üzərindən 24 saat fasiləsiz xidmət göstərir</p>
        
        <div class="info-grid">
            <div class="info-card">
                <span class="label">🤖 Bot İstifadəçi Adı</span>
                <span class="val">@Anbarbotu_bot</span>
            </div>
            <div class="info-card">
                <span class="label">⏱️ İşləmə Müddəti</span>
                <span class="val">{{ uptime }}</span>
            </div>
            <div class="info-card">
                <span class="label">🌐 Server Portu</span>
                <span class="val">{{ port }}</span>
            </div>
            <div class="info-card">
                <span class="label">📊 Excel Məlumatı</span>
                <span class="val">{{ excel_status }}</span>
            </div>
        </div>

        <a href="https://t.me/Anbarbotu_bot" target="_blank" class="btn-link">
            💬 Telegram-da Bota Keçid Et
        </a>

        <p class="footer-note">💡 Render Free Tier 7/24 istifadəsi üçün <code>/health</code> linkini UptimeRobot-a əlavə edin.</p>
    </div>
</body>
</html>
"""

SCANNER_HTML = """

<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>📷 Barkod Skaneri - Dore Group</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background: #0f172a;
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px;
        }
        .header {
            width: 100%;
            max-width: 450px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        h1 { font-size: 1.25rem; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
        #reader {
            width: 100%;
            max-width: 450px;
            border-radius: 20px;
            overflow: hidden;
            border: 2px solid #38bdf8;
            box-shadow: 0 10px 25px rgba(56, 189, 248, 0.2);
            background: #000;
        }
        .result-card {
            width: 100%;
            max-width: 450px;
            margin-top: 16px;
            background: rgba(30, 41, 59, 0.9);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 18px;
            padding: 18px;
            display: none;
            animation: slideUp 0.3s ease;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .product-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; color: #fff; }
        .info-row { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.95rem; }
        .label { color: #94a3b8; }
        .val { font-weight: 600; color: #e2e8f0; }
        .price { color: #4ade80; font-size: 1.15rem; font-weight: 700; }
        .stock-badge { padding: 3px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; }
        .stock-good { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .stock-low { background: rgba(234, 179, 8, 0.2); color: #facc15; }
        .stock-zero { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .btn-action {
            display: block;
            width: 100%;
            padding: 12px;
            margin-top: 12px;
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: #fff;
            text-align: center;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            border: none;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-action:hover { opacity: 0.9; transform: scale(0.99); }
        .btn-rescan {
            background: rgba(255, 255, 255, 0.1);
            color: #cbd5e1;
            margin-top: 8px;
        }
        .status-pill {
            margin-top: 10px;
            font-size: 0.85rem;
            color: #64748b;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📷 Barkod Skaneri</h1>
        <span style="font-size: 0.85rem; color: #94a3b8;">Dore Group MMC</span>
    </div>

    <div id="reader"></div>

    <div class="result-card" id="resultCard">
        <div class="product-title" id="pName">Məhsul Adı</div>
        <div class="info-row">
            <span class="label">🏷️ Brend:</span>
            <span class="val" id="pBrand">-</span>
        </div>
        <div class="info-row">
            <span class="label">🆔 Kod:</span>
            <span class="val" id="pCode">-</span>
        </div>
        <div class="info-row">
            <span class="label">📊 Barkod:</span>
            <span class="val" id="pBarcode">-</span>
        </div>
        <div class="info-row">
            <span class="label">💵 Qiymət:</span>
            <span class="price" id="pPrice">0.00 AZN</span>
        </div>
        <div class="info-row">
            <span class="label">📦 Qalıq:</span>
            <span id="pStockBadge" class="stock-badge stock-good">0 əd</span>
        </div>

        <button class="btn-action" id="btnSend">💬 Bota Göndər</button>
        <button class="btn-action btn-rescan" id="btnRescan">🔄 Yenidən Skan Et</button>
    </div>

    <div style="margin-top: 12px; width: 100%; max-width: 450px;">
        <input type="file" id="qrFileInput" accept="image/*" style="display: none;">
        <button class="btn-action" style="background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15);" id="btnUploadImage">🖼️ Qalereyadan Şəkil Seç</button>
    </div>

    <div class="status-pill" id="statusText">Barkodu kameranın çərçivəsinə yaxınlaşdırın</div>

    <script>
        const urlParams = new URLSearchParams(window.location.search);
        // Əgər linkdə chat_id ötürülməyibsə, birbaşa Dore Group MMC qrupuna (-1003749180365) göndərir
        const chatId = urlParams.get('chat_id') || '-1003749180365';
        const threadId = urlParams.get('thread_id');
        const userName = urlParams.get('user_name') || '';

        if (window.Telegram && window.Telegram.WebApp) {
            try {
                Telegram.WebApp.ready();
                Telegram.WebApp.expand();
            } catch(e) {}
        }

        document.getElementById("btnSend").innerText = "💬 Qrupa Göndər";

        let html5QrCode = null;
        let lastScannedCode = "";

        function startScanner() {
            document.getElementById("resultCard").style.display = "none";
            document.getElementById("reader").style.display = "block";
            document.getElementById("btnUploadImage").style.display = "block";
            document.getElementById("statusText").innerText = "Barkodu kameranın çərçivəsinə yaxınlaşdırın";

            if (!html5QrCode) {
                html5QrCode = new Html5Qrcode("reader");
            }

            const config = {
                fps: 15,
                qrbox: { width: 260, height: 160 },
                aspectRatio: 1.0
            };

            html5QrCode.start(
                { facingMode: "environment" },
                config,
                onScanSuccess
            ).catch(err => {
                document.getElementById("statusText").innerText = "⚠️ Kamera icazəsi tələb olunur və ya kamera tapılmadı. Şəkli aşağıdan yükləyə bilərsiniz.";
            });
        }

        function onScanSuccess(decodedText) {
            if (decodedText === lastScannedCode) return;
            lastScannedCode = decodedText;

            if (navigator.vibrate) navigator.vibrate(80);

            if (html5QrCode && html5QrCode.isScanning) {
                html5QrCode.stop().then(() => {
                    lookupProduct(decodedText);
                }).catch(() => {
                    lookupProduct(decodedText);
                });
            } else {
                lookupProduct(decodedText);
            }
        }

        function lookupProduct(barcode) {
            document.getElementById("statusText").innerText = "🔎 Məlumat axtarılır: " + barcode;
            
            fetch('/api/search?q=' + encodeURIComponent(barcode))
                .then(r => r.json())
                .then(data => {
                    if (data.found && data.product) {
                        const p = data.product;
                        document.getElementById("pName").innerText = p.name;
                        document.getElementById("pBrand").innerText = p.brand || "-";
                        document.getElementById("pCode").innerText = p.code || "-";
                        document.getElementById("pBarcode").innerText = p.barcode || barcode;
                        document.getElementById("pPrice").innerText = p.price + " AZN";

                        const qty = parseFloat(p.stock) || 0;
                        const badge = document.getElementById("pStockBadge");
                        if (qty <= 0) {
                            badge.className = "stock-badge stock-zero";
                            badge.innerText = "Bitib (0 əd)";
                        } else if (qty <= 5) {
                            badge.className = "stock-badge stock-low";
                            badge.innerText = qty + " əd (Az qalıb!)";
                        } else {
                            badge.className = "stock-badge stock-good";
                            badge.innerText = qty + " əd";
                        }

                        document.getElementById("reader").style.display = "none";
                        document.getElementById("btnUploadImage").style.display = "none";
                        document.getElementById("resultCard").style.display = "block";
                        document.getElementById("statusText").innerText = "✅ Məhsul tapıldı!";
                    } else {
                        document.getElementById("pName").innerText = "Naməlum Məhsul";
                        document.getElementById("pBrand").innerText = "-";
                        document.getElementById("pCode").innerText = "-";
                        document.getElementById("pBarcode").innerText = barcode;
                        document.getElementById("pPrice").innerText = "Tapılmadı";
                        const badge = document.getElementById("pStockBadge");
                        badge.className = "stock-badge stock-zero";
                        badge.innerText = "Bazada yoxdur";

                        document.getElementById("reader").style.display = "none";
                        document.getElementById("btnUploadImage").style.display = "none";
                        document.getElementById("resultCard").style.display = "block";
                        document.getElementById("statusText").innerText = "⚠️ Bu barkodla məhsul tapılmadı.";
                    }
                })
                .catch(() => {
                    document.getElementById("statusText").innerText = "Skan edildi: " + barcode;
                });
        }

        document.getElementById("btnUploadImage").addEventListener("click", () => {
            document.getElementById("qrFileInput").click();
        });

        document.getElementById("qrFileInput").addEventListener("change", e => {
            const file = e.target.files[0];
            if (!file) return;

            document.getElementById("statusText").innerText = "🖼️ Şəkil yoxlanılır...";
            if (!html5QrCode) {
                html5QrCode = new Html5Qrcode("reader");
            }

            html5QrCode.scanFile(file, true)
                .then(decodedText => {
                    onScanSuccess(decodedText);
                })
                .catch(err => {
                    document.getElementById("statusText").innerText = "⚠️ Şəkildə barkod aşkar edilmədi. Zəhmət olmasa daha aydın şəkil seçin.";
                });
        });

        document.getElementById("btnSend").addEventListener("click", () => {
            if (!lastScannedCode) return;

            const btn = document.getElementById("btnSend");
            btn.disabled = true;
            btn.style.opacity = "0.75";
            btn.innerText = "⏳ Qrupa Göndərilir...";
            document.getElementById("statusText").innerText = "⏳ Məlumat qrupa göndərilir, xahiş olunur gözləyin...";

            const senderName = userName || (window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name || 'İstifadəçi');
            
            fetch('/api/send_result', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chat_id: chatId,
                    thread_id: threadId,
                    barcode: lastScannedCode,
                    user_name: senderName
                })
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.background = "linear-gradient(135deg, #16a34a 0%, #15803d 100%)";
                    btn.innerText = "✅ Qrupa Uğurla Göndərildi!";
                    document.getElementById("statusText").innerText = "🎉 Məlumat Dore Group MMC qrupuna göndərildi!";

                    // Əgər qrupa qayıt düyməsi yoxdursa əlavə edirik
                    if (!document.getElementById("btnReturn")) {
                        const returnBtn = document.createElement("a");
                        returnBtn.id = "btnReturn";
                        returnBtn.className = "btn-action";
                        returnBtn.style.background = "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)";
                        returnBtn.style.marginTop = "10px";
                        returnBtn.href = "https://t.me/Doregroupmmc";
                        returnBtn.innerText = "💬 Telegram Qrupuna Qayıt";
                        document.getElementById("resultCard").appendChild(returnBtn);
                    }

                    // Əgər Telegram WebApp daxilindədirsə bağlamağa çalışırıq
                    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
                        try { Telegram.WebApp.close(); } catch(e) {}
                    }
                } else {
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.background = "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)";
                    btn.innerText = "⚠️ Xəta: Təkrar Cəhd Edin";
                    document.getElementById("statusText").innerText = "⚠️ Göndərilmədi: " + (res.error || "Xəta baş verdi");
                }
            })
            .catch(err => {
                btn.disabled = false;
                btn.style.opacity = "1";
                btn.style.background = "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)";
                btn.innerText = "⚠️ Şəbəkə Xətası: Təkrar Cəhd Edin";
                document.getElementById("statusText").innerText = "⚠️ Şəbəkə xətası baş verdi. İnternet bağlantınızı yoxlayın.";
            });
        });

        document.getElementById("btnRescan").addEventListener("click", () => {
            lastScannedCode = "";
            const btn = document.getElementById("btnSend");
            btn.disabled = false;
            btn.style.opacity = "1";
            btn.style.background = "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)";
            btn.innerText = "💬 Qrupa Göndər";
            const ret = document.getElementById("btnReturn");
            if (ret) ret.remove();
            startScanner();
        });

        window.addEventListener("load", () => {
            startScanner();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    uptime_sec = int(time.time() - start_time)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}s {minutes}d {seconds}san"
    
    excel_info = "Yüklənib" if bot.DATA_CACHE["df"] is not None else "Aktiv"
    port = os.environ.get("PORT", "7860")
    
    return render_template_string(HTML_TEMPLATE, uptime=uptime_str, port=port, excel_status=excel_info)

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "bot": "running",
        "uptime": int(time.time() - start_time),
        "has_token": bool(bot.TELEGRAM_TOKEN),
        "token_len": len(bot.TELEGRAM_TOKEN or "")
    }), 200

@app.route('/scanner')
def scanner():
    return render_template_string(SCANNER_HTML)


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"found": False, "product": None})

    try:
        df, err = bot.datani_yukle()
        if err or df is None:
            return jsonify({"found": False, "product": None})

        results = bot.bazada_axtar(q)
        if not results or "Uyğun məhsul tapılmadı" in results[0][0]:
            return jsonify({"found": False, "product": None})

        caption = results[0][0]
        lines = caption.split("\n")
        data = {}
        for l in lines:
            if "Kod:" in l: data["code"] = l.split("Kod:")[-1].replace("*", "").replace("`", "").strip()
            if "Məhsul:" in l: data["name"] = l.split("Məhsul:")[-1].replace("*", "").replace("`", "").strip()
            if "Brend:" in l: data["brand"] = l.split("Brend:")[-1].replace("*", "").replace("`", "").strip()
            if "Qiymət:" in l: data["price"] = l.split("Qiymət:")[-1].replace("*", "").replace("`", "").replace("AZN", "").strip()
            if "Barkod:" in l: data["barcode"] = l.split("Barkod:")[-1].replace("*", "").replace("`", "").strip()
            if "Qalıq:" in l: data["stock"] = l.split("Qalıq:")[-1].replace("*", "").replace("`", "").strip()

        return jsonify({"found": True, "product": data})
    except Exception as e:
        return jsonify({"found": False, "error": str(e)})

@app.route('/api/send_result', methods=['POST'])
def api_send_result():
    """WebApp skanerindən qəbul edilmiş barkod nəticəsini qrupa və ya çata göndərən API"""
    try:
        data = request.get_json(force=True) or {}
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        barcode = (data.get('barcode') or '').strip()
        user_name = data.get('user_name') or 'İstifadəçi'

        if not chat_id or not barcode:
            return jsonify({"success": False, "error": "chat_id və ya barcode çatışmır"}), 400

        try:
            chat_id = int(chat_id)
        except Exception:
            pass

        if thread_id:
            try:
                thread_id = int(thread_id)
            except Exception:
                thread_id = None

        results = bot.bazada_axtar(barcode)
        if not results or "Uyğun məhsul tapılmadı" in results[0][0]:
            fail_text = (
                f"📷 **Barkod Skan Edildi:** `{barcode}`\n"
                f"👤 **İstifadəçi:** {user_name}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ Bu barkodla anbar bazasında məhsul tapılmadı."
            )
            bot.safe_send_message(chat_id, fail_text, thread_id=thread_id)
            return jsonify({"success": True, "found": False})

        header = f"📷 **Barkod Skan Edildi:** `{barcode}`\n👤 **İstifadəçi:** {user_name}\n━━━━━━━━━━━━━━━━━━━━\n"

        for res in results:
            if isinstance(res, (tuple, list)):
                caption = str(res[0]) if len(res) > 0 else ""
                inline_markup = res[1] if len(res) > 1 and isinstance(res[1], bot.types.InlineKeyboardMarkup) else None
            else:
                caption = str(res)
                inline_markup = None

            full_caption = header + caption if caption else header
            sent_msg = bot.safe_send_message(chat_id, full_caption, reply_markup=inline_markup, thread_id=thread_id)
            if not sent_msg:
                bot.safe_print(f"❌ api_send_result: Telegram-a mesaj göndərilə bilmədi (Chat: {chat_id})")
                return jsonify({"success": False, "error": "Telegram API mesajı qəbul etmədi. Botun qrupdakı icazələrini və ya tokeni yoxlayın."}), 500

        return jsonify({"success": True, "found": True})
    except Exception as e:
        bot.safe_print(f"❌ api_send_result xətası: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"🌐 Veb Server başladılır (Port: {port})...")
    app.run(host="0.0.0.0", port=port)

