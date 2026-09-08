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

    if hasattr(bot, "CHAT_MESSAGES") and isinstance(bot.CHAT_MESSAGES, dict):
        print("  ✅ CHAT_MESSAGES çat izləmə sistemi aktivdir.")
        passed += 1
    else:
        print("  ❌ CHAT_MESSAGES mövcud deyil!")
        failed += 1

    if hasattr(bot, "handle_clear_chat") and callable(bot.handle_clear_chat):
        print("  ✅ handle_clear_chat qrup təmizləmə funksiyası aktivdir.")
        passed += 1
    else:
        print("  ❌ handle_clear_chat funksiyası tapılmadı!")
        failed += 1

    if hasattr(bot, "SCANNER_URL") and bot.SCANNER_URL:
        print(f"  ✅ SCANNER_URL WebApp konfiqurasiya edilib: {bot.SCANNER_URL}")
        passed += 1
    else:
        print("  ❌ SCANNER_URL tapılmadı!")
        failed += 1

    if hasattr(bot, "CONTACTS_INFO") and bot.CONTACTS_INFO:
        print("  ✅ CONTACTS_INFO əlaqə və şöbələr məlumatı aktivdir.")
        passed += 1
    else:
        print("  ❌ CONTACTS_INFO tapılmadı!")
        failed += 1

    if hasattr(bot, "PENDING_ANNOUNCEMENTS") and isinstance(bot.PENDING_ANNOUNCEMENTS, dict):
        print("  ✅ PENDING_ANNOUNCEMENTS qrup elan sistemi aktivdir.")
        passed += 1
    else:
        print("  ❌ PENDING_ANNOUNCEMENTS tapılmadı!")
        failed += 1

    # Test 5: Çoxistifadəçili Rejim və İnteraktiv Vərəqləmə (Pagination) Testi
    print("\n5. Çoxistifadəçili Vərəqləmə (Pagination) və Reply Testi:")
    try:
        from unittest.mock import MagicMock
        sent_items = []
        def mock_send(chat_id, text, reply_markup=None, thread_id=None, reply_to_message_id=None, track=True, parse_mode="Markdown"):
            sent_items.append({'chat_id': chat_id, 'text': text, 'reply_to': reply_to_message_id, 'markup': reply_markup})
            res = MagicMock()
            res.message_id = len(sent_items)
            return res

        orig_send = bot.safe_send_message
        bot.safe_send_message = mock_send

        # 1-ci istifadəçi (Paşa) axtarış edir
        m1 = MagicMock()
        m1.chat.id = -100123456
        m1.chat.type = 'group'
        m1.message_id = 701
        m1.from_user.id = 101
        m1.from_user.first_name = 'Paşa'
        m1.text = '1034'
        m1.message_thread_id = None
        bot.handle_message(m1)

        # 2-ci istifadəçi (Elnada) eyni anda eyni malı axtarır
        m2 = MagicMock()
        m2.chat.id = -100123456
        m2.chat.type = 'group'
        m2.message_id = 702
        m2.from_user.id = 102
        m2.from_user.first_name = 'Elnada'
        m2.text = '1034'
        m2.message_thread_id = None
        bot.handle_message(m2)

        bot.safe_send_message = orig_send

        if len(sent_items) == 2:
            print("  ✅ 2 fərqli istifadəçi üçün 2 ayrı cavab göndərildi.")
            passed += 1
        else:
            print(f"  ❌ Gözlənilən 2 cavab idi, amma {len(sent_items)} göndərildi.")
            failed += 1

        if sent_items[0]['reply_to'] == 701 and sent_items[1]['reply_to'] == 702:
            print("  ✅ Hər cavab birbaşa aid olduğu istifadəçinin mesajına Reply edildi (701 və 702).")
            passed += 1
        else:
            print("  ❌ Reply-to-message ID-ləri uyğun gəlmədi!")
            failed += 1

        if "Paşa" in sent_items[0]['text'] and "Elnada" in sent_items[1]['text']:
            print("  ✅ Hər cavabın başında düzgün istifadəçi etiketi (Header Tag) qeyd edildi.")
            passed += 1
        else:
            print("  ❌ İstifadəçi etiketləri tapılmadı!")
            failed += 1

        if "Paşa tərəfindən də soruşulmuşdu" in sent_items[1]['text']:
            print("  ✅ Eyni mal təkrar axtarıldıqda avtomatik təkrar qeydi çıxdı.")
            passed += 1
        else:
            print("  ❌ Təkrar axtarış qeydi çıxmadı!")
            failed += 1

        # Vərəqləmə (Callback) testi
        pasa_sess = [k for k, v in bot.SEARCH_SESSIONS.items() if v.get('user_name') == 'Paşa']
        if pasa_sess:
            sess_id = pasa_sess[-1]
            call_mock = MagicMock()
            call_mock.data = f"nav:{sess_id}:1"
            call_mock.message.chat.id = -100123456
            call_mock.message.message_id = 1
            call_mock.id = "c1"

            edited = []
            def mock_edit(text, cid, mid, reply_markup=None, parse_mode=None):
                edited.append({'text': text, 'markup': reply_markup})

            orig_edit = bot.tg_bot.edit_message_text
            bot.tg_bot.edit_message_text = mock_edit
            bot.tg_bot.answer_callback_query = MagicMock()

            bot.handle_pagination_callback(call_mock)
            bot.tg_bot.edit_message_text = orig_edit

            if len(edited) == 1 and "2 /" in edited[0]['text']:
                print("  ✅ 'Növbəti' düyməsinə toxunulduqda mesaj yerindəcə 2-ci məhsula vərəqləndi.")
                passed += 1
            else:
                print("  ❌ Vərəqləmə (Pagination) edit uğursuz oldu!")
                failed += 1
        else:
            print("  ❌ Paşa üçün axtarış sessiyası tapılmadı!")
            failed += 1

    except Exception as ex:
        print(f"  ❌ Test 5 xətası: {ex}")
        failed += 1

    print("\n" + "="*40)


    print(f"📊 TEST NƏTİCƏSİ: {passed} Uğurlu, {failed} Xətalı")
    if failed == 0:
        print("🎉 BÜTÜN TESTLƏR UĞURLA KEÇDİ!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
