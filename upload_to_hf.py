import os
import glob
import sys
from huggingface_hub import HfApi

# Windows konsolunda UTF-8 dəstəyi
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

REPO_ID = "Orxam91/Anbar_bot"

def fayli_tap():
    current_folder = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(current_folder, "*.xlsx"))
    for f in files:
        fname = os.path.basename(f).lower()
        if "mehsul" in fname or "anbar" in fname:
            return f
    return files[0] if files else None

def upload():
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    excel_path = fayli_tap()
    
    print(f"🔄 Hugging Face-ə yenilənmə göndərilir: {REPO_ID}...")
    
    try:
        # 1. README.md yenilənir
        if os.path.exists("README.md"):
            api.upload_file(
                path_or_fileobj="README.md",
                path_in_repo="README.md",
                repo_id=REPO_ID,
                repo_type="space"
            )
            print("✅ README.md yeniləndi.")

        # 2. bot.py yenilənir
        if os.path.exists("bot.py"):
            api.upload_file(
                path_or_fileobj="bot.py",
                path_in_repo="bot.py",
                repo_id=REPO_ID,
                repo_type="space"
            )
            print("✅ bot.py yeniləndi.")

        # 3. app.py yenilənir
        if os.path.exists("app.py"):
            api.upload_file(
                path_or_fileobj="app.py",
                path_in_repo="app.py",
                repo_id=REPO_ID,
                repo_type="space"
            )
            print("✅ app.py yeniləndi.")

        # 4. requirements.txt yenilənir
        if os.path.exists("requirements.txt"):
            api.upload_file(
                path_or_fileobj="requirements.txt",
                path_in_repo="requirements.txt",
                repo_id=REPO_ID,
                repo_type="space"
            )
            print("✅ requirements.txt yeniləndi.")

        # 5. Excel faylı yenilənir
        if excel_path:
            fname = os.path.basename(excel_path)
            api.upload_file(
                path_or_fileobj=excel_path,
                path_in_repo=fname,
                repo_id=REPO_ID,
                repo_type="space"
            )
            print(f"✅ Excel faylı yeniləndi: {fname}")

        print("\n🎉 BÜTÜN DƏYİŞİKLİKLƏR UĞURLA HUGGING FACE-Ə YÜKLƏNDİ VƏ BOT 7/24 YENİLƏNDİ!")
    except Exception as e:
        print(f"\n⚠️ Hugging Face yükləmə xətası: {e}")
        print("💡 Qeyd: Yükləmə üçün HF_TOKEN mühit dəyişənini daxil etdiyinizə və ya repo id-in düzgünlüyünə əmin olun.")

if __name__ == "__main__":
    upload()
