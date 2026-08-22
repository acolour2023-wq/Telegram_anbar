import os
import threading
import time
import socket
from flask import Flask, render_template_string, jsonify
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
        "uptime": int(time.time() - start_time)
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"🌐 Veb Server başladılır (Port: {port})...")
    app.run(host="0.0.0.0", port=port)
