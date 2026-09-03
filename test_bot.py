import sys
import os

# Set UTF-8 encoding for test output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import bot

def run_tests():
    print("🧪 BOT TEST SÜİTİ BAŞLADILIR...\n" + "="*40)
    passed = 0
    failed = 0

    # Test 1: Normalization
    print("1. Text Normalization Testi:")
    test_cases = [
        ("NUR GİDA", "nur gida"),
        ("MƏHSUL QALIĞI", "mehsul qaligi"),
        ("Şokolad Yağı (20%)+", "sokolad yagi (20%)+")
    ]
    for inp, expected in test_cases:
        res = bot.az_normalize(inp)
        if res == expected:
            print(f"  ✅ '{inp}' -> '{res}'")
            passed += 1
        else:
            print(f"  ❌ '{inp}' -> '{res}' (gözlənilən: '{expected}')")
            failed += 1

    # Test 2: Data loading
    print("\n2. Excel Məlumat Yükləmə Testi:")
    df, err = bot.datani_yukle()
    if err is None and df is not None and len(df) > 0:
        print(f"  ✅ Excel uğurla yükləndi ({len(df)} sətir).")
        passed += 1
    else:
        print(f"  ❌ Excel yükləmə xətası: {err}")
        failed += 1

    # Test 3: Search function structure and output guarantee
    print("\n3. Bazada Axtarış və Output Format Qarantiyası Testi:")
    queries = ["10002", "1034", "0679", "", "   ", "nonexistent999999", "NUR GİDA", "smart"]
    for q in queries:
        results = bot.bazada_axtar(q)
        if not isinstance(results, list) or len(results) == 0:
            print(f"  ❌ Qeyri-kafi nəticə formatı query: '{q}'")
            failed += 1
            continue
        
        valid_structure = True
        for item in results:
            if not (isinstance(item, tuple) or isinstance(item, list)) or len(item) < 2:
                valid_structure = False
                break
        
        if valid_structure:
            print(f"  ✅ Query '{q}' -> {len(results)} nəticə (Hər biri 2-tuple formatındadır)")
            passed += 1
        else:
            print(f"  ❌ Query '{q}' üçün invalid tuple strukturu qaytarıldı!")
            failed += 1

    # Test 4: Admin and Security Settings
    print("\n4. Admin və Təhlükəsizlik Testi:")
    if hasattr(bot, "ADMIN_PASSWORD") and bot.ADMIN_PASSWORD:
        print(f"  ✅ Admin şifrəsi təyin edilib: {bot.ADMIN_PASSWORD}")
        passed += 1
    else:
        print("  ❌ Admin şifrəsi tapılmadı!")
        failed += 1

    if hasattr(bot, "PENDING_UPLOADS") and isinstance(bot.PENDING_UPLOADS, dict):
        print("  ✅ PENDING_UPLOADS təhlükəsiz vəziyyət lüğəti aktivdir.")
        passed += 1
    else:
        print("  ❌ PENDING_UPLOADS mövcud deyil!")
        failed += 1

    print("\n" + "="*40)
    print(f"📊 TEST NƏTİCƏSİ: {passed} Uğurlu, {failed} Xətalı")
    if failed == 0:
        print("🎉 BÜTÜN TESTLƏR UĞURLA KEÇDİ!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
