import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def add_imports(filepath, new_imports):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "from bot.messages import (" in content:
        # insert inside the parens
        parts = content.split("from bot.messages import (", 1)
        new_content = parts[0] + "from bot.messages import (\n    " + ",\n    ".join(new_imports) + ",\n" + parts[1].lstrip('\n')
    else:
        # append to existing imports or beginning of file
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from bot.messages import"):
                insert_idx = i
                break
        
        if insert_idx != 0:
            existing = lines[insert_idx]
            new_import_str = "from bot.messages import (\n    " + existing.split("import ")[1] + ",\n    " + ",\n    ".join(new_imports) + ",\n)"
            lines[insert_idx] = new_import_str
            new_content = '\n'.join(lines)
        else:
            new_import_str = "from bot.messages import (\n    " + ",\n    ".join(new_imports) + ",\n)"
            new_content = new_import_str + "\n" + content
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

def do_replacements():
    # 1. watchdog.py
    replacements_watchdog = [
        ('"❌ Job Queue غير متاح"', 'WATCHDOG_QUEUE_UNAVAILABLE'),
        ('"✅ مراقبة الراوترات تعمل بالفعل"', 'WATCHDOG_ALREADY_RUNNING'),
        ('"✅ تم بدء مراقبة الراوترات (كل 5 دقائق)"', 'WATCHDOG_STARTED'),
        ('"❌ تم إيقاف مراقبة الراوترات"', 'WATCHDOG_STOPPED'),
        ('"📭 لا توجد روترات محفوظة"', 'WATCHDOG_NO_ROUTERS'),
        ('["📊 \u003cb\u003eحالة الراوترات:\u003c/b\u003e\\n"]', '[WATCHDOG_STATUS_HEADER]'),
        ('f"آخر اتصال: {last_ok.strftime(\'%Y-%m-%d %H:%M\')}"', 'WATCHDOG_LAST_OK.format(date=last_ok.strftime("%Y-%m-%d %H:%M"))'),
        ('"متصل"', 'WATCHDOG_ONLINE'),
        ('f"آخر فشل: {last_fail.strftime(\'%Y-%m-%d %H:%M\')}"', 'WATCHDOG_LAST_FAIL.format(date=last_fail.strftime("%Y-%m-%d %H:%M"))'),
        ('"لم يتم الفحص بعد"', 'WATCHDOG_NOT_CHECKED'),
        ('f"   ├─ الإصدار: {version}"', 'WATCHDOG_VERSION.format(version=version)'),
        ('f"   ├─ مستخدمو Hotspot النشطون: {active_text}"', 'WATCHDOG_ACTIVE_HOTSPOT.format(count=active_text)'),
        ('f"   └─ آخر نسخة احتياطية: {backup_text}\\n"', 'WATCHDOG_LAST_BACKUP.format(backup=backup_text)'),
        ('"🔄 تحديث فوري (Live Ping)"', 'WATCHDOG_REFRESH_BTN'),
        ('"🔙 رجوع"', 'WATCHDOG_BACK_BTN'),
        ('"⏳ جاري الفحص الحي للراوترات..."', 'WATCHDOG_REFRESHING'),
        ('f"🔴 الروتر \u003cb\u003e{identity}\u003c/b\u003e غير متصل!"', 'WATCHDOG_OFFLINE_ALERT.format(identity=identity)'),
        ('f"🟢 الروتر \u003cb\u003e{identity}\u003c/b\u003e عاد للاتصال"', 'WATCHDOG_ONLINE_ALERT.format(identity=identity)')
    ]
    if replace_in_file("bot/handlers/watchdog.py", replacements_watchdog):
        add_imports("bot/handlers/watchdog.py", ["WATCHDOG_QUEUE_UNAVAILABLE", "WATCHDOG_ALREADY_RUNNING", "WATCHDOG_STARTED", "WATCHDOG_STOPPED", "WATCHDOG_NO_ROUTERS", "WATCHDOG_STATUS_HEADER", "WATCHDOG_LAST_OK", "WATCHDOG_ONLINE", "WATCHDOG_LAST_FAIL", "WATCHDOG_NOT_CHECKED", "WATCHDOG_VERSION", "WATCHDOG_ACTIVE_HOTSPOT", "WATCHDOG_LAST_BACKUP", "WATCHDOG_REFRESH_BTN", "WATCHDOG_BACK_BTN", "WATCHDOG_REFRESHING", "WATCHDOG_OFFLINE_ALERT", "WATCHDOG_ONLINE_ALERT"])

    # 2. userman_search.py
    replacements_userman_search = [
        ('" [🔴 معطل]"', 'USERMAN_SEARCH_OFFLINE'),
        ('f"🔍 تم العثور على {len(users)}"', 'USERMAN_SEARCH_FOUND.format(count=len(users))'),
        ('f" — يعرض أول {MAX_SEARCH_RESULTS}:"', 'USERMAN_SEARCH_LIMIT.format(limit=MAX_SEARCH_RESULTS)'),
        ('"🔴 معطل"', 'USERMAN_SEARCH_STATUS_OFF'),
        ('"🟢 نشط"', 'USERMAN_SEARCH_STATUS_ON'),
        ('f"👤 مستخدم User Manager:\\n📛 الاسم: {name}\\n🔑 الرمز: {pwd}\\n📋 البروفايل: {profile}\\nوضع الحساب: {status}"', 'USERMAN_SEARCH_RESULT.format(name=name, pwd=pwd, profile=profile, status=status)'),
        ('"جاري البحث..."', 'USERMAN_SEARCH_LOADING'),
        ('"⚠️ انتهت الجلسة أو بيانات غير صالحة."', 'USERMAN_SEARCH_SESSION_EXPIRED'),
        ('f"✅ تم طرد {killed} جلسة للمستخدم {username}."', 'USERMAN_SEARCH_KICKED.format(killed=killed, username=username)'),
        ('f"✅ تم تصفير عداد المستخدم {username}."', 'USERMAN_SEARCH_RESET.format(username=username)'),
        ('f"✅ تم تفعيل المستخدم {username}."', 'USERMAN_SEARCH_ENABLED.format(username=username)'),
        ('f"🔴 تم تعطيل المستخدم {username}."', 'USERMAN_SEARCH_DISABLED.format(username=username)'),
        ('f"🗑️ تم حذف المستخدم {username}."', 'USERMAN_SEARCH_DELETED.format(username=username)'),
        ('f"❌ خطأ: {e}"', 'USERMAN_SEARCH_ERROR.format(e=e)'),
        ('"غير معروف"', 'USERMAN_SEARCH_UNKNOWN_ERR')
    ]
    if replace_in_file("bot/handlers/userman_search.py", replacements_userman_search):
        add_imports("bot/handlers/userman_search.py", ["USERMAN_SEARCH_OFFLINE", "USERMAN_SEARCH_FOUND", "USERMAN_SEARCH_LIMIT", "USERMAN_SEARCH_STATUS_OFF", "USERMAN_SEARCH_STATUS_ON", "USERMAN_SEARCH_RESULT", "USERMAN_SEARCH_LOADING", "USERMAN_SEARCH_SESSION_EXPIRED", "USERMAN_SEARCH_KICKED", "USERMAN_SEARCH_RESET", "USERMAN_SEARCH_ENABLED", "USERMAN_SEARCH_DISABLED", "USERMAN_SEARCH_DELETED", "USERMAN_SEARCH_ERROR", "USERMAN_SEARCH_UNKNOWN_ERR"])

    # 3. userman.py
    replacements_userman = [
        ('"غير محدد"', 'USERMAN_PAYMENT_UNSPECIFIED'),
        ('f"\\n\\n⚠️ {unlinked_count} من {len(cards)} كارتاً لم يُربط بها البروفايل "', 'USERMAN_UNLINKED_WARNING.format(unlinked=unlinked_count, total=len(cards))')
    ]
    if replace_in_file("bot/handlers/userman.py", replacements_userman):
        add_imports("bot/handlers/userman.py", ["USERMAN_PAYMENT_UNSPECIFIED", "USERMAN_UNLINKED_WARNING"])

    # 4. usage.py
    replacements_usage = [
        ('"⚠️ لم يتم اختيار روتر"', 'USAGE_NO_ROUTER'),
        ('f"الحالة: {status}"', 'USAGE_STATUS.format(status=status)')
    ]
    if replace_in_file("bot/handlers/usage.py", replacements_usage):
        add_imports("bot/handlers/usage.py", ["USAGE_NO_ROUTER", "USAGE_STATUS"])

    # 5. timeout.py
    replacements_timeout = [
        ('("5 دقائق", 5)', '(TIMEOUT_MINS_5, 5)'),
        ('("15 دقيقة", 15)', '(TIMEOUT_MINS_15, 15)'),
        ('("30 دقيقة", 30)', '(TIMEOUT_MINS_30, 30)'),
        ('("60 دقيقة", 60)', '(TIMEOUT_MINS_60, 60)'),
        ('("بدون إغلاق", 0)', '(TIMEOUT_NO_LIMIT, 0)'),
        ('"❌ إلغاء"', 'TIMEOUT_CANCEL_BTN'),
        ('"⏰ \u003cb\u003eإعداد مدة الخمول (Session Timeout)\u003c/b\u003e\\n\\nاختر المدة التي سيتم بعدها إغلاق الجلسة وإجبارك على اختيار الراوتر مجدداً (لحماية النظام):"', 'TIMEOUT_HEADER'),
        ('"✅ تم حفظ إعداد الخمول بنجاح.\\nالمدة الحالية: "', 'TIMEOUT_SAVED'),
        ('"بدون إغلاق (مفتوح دائماً)."', 'TIMEOUT_SAVED_NO_LIMIT'),
        ('f"{val} دقيقة."', 'TIMEOUT_SAVED_MINS.format(val=val)'),
        ('"❌ حدث خطأ أثناء حفظ الإعداد."', 'TIMEOUT_SAVE_ERROR')
    ]
    if replace_in_file("bot/handlers/timeout.py", replacements_timeout):
        add_imports("bot/handlers/timeout.py", ["TIMEOUT_MINS_5", "TIMEOUT_MINS_15", "TIMEOUT_MINS_30", "TIMEOUT_MINS_60", "TIMEOUT_NO_LIMIT", "TIMEOUT_CANCEL_BTN", "TIMEOUT_HEADER", "TIMEOUT_SAVED", "TIMEOUT_SAVED_NO_LIMIT", "TIMEOUT_SAVED_MINS", "TIMEOUT_SAVE_ERROR"])

do_replacements()
print("Replacements for batch 3 done.")
