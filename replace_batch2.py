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
    # 1. backup_restore.py
    replacements_br = [
        ('USERMAN_RESTORE_FAILED.format(error="اسم ملف الاستعادة غير صالح")', 'USERMAN_RESTORE_FAILED.format(error=BACKUP_RESTORE_INVALID_NAME)'),
        ('USERMAN_RESTORE_FAILED.format(error="الملف غير موجود")', 'USERMAN_RESTORE_FAILED.format(error=BACKUP_RESTORE_NOT_FOUND)'),
        ('f"📋 {result[\'profiles_restored\']} بروفايل"', 'BACKUP_RESTORE_PROFILES_COUNT.format(count=result["profiles_restored"])'),
        ('f"👥 {result[\'users_restored\']} مستخدم"', 'BACKUP_RESTORE_USERS_COUNT.format(count=result["users_restored"])'),
        ('f"⏭️ {skipped} تم تخطيها"', 'BACKUP_RESTORE_SKIPPED.format(skipped=skipped)'),
        ('"لا شيء"', 'BACKUP_RESTORE_NONE')
    ]
    if replace_in_file("bot/handlers/backup_restore.py", replacements_br):
        add_imports("bot/handlers/backup_restore.py", ["BACKUP_RESTORE_INVALID_NAME", "BACKUP_RESTORE_NOT_FOUND", "BACKUP_RESTORE_PROFILES_COUNT", "BACKUP_RESTORE_USERS_COUNT", "BACKUP_RESTORE_SKIPPED", "BACKUP_RESTORE_NONE"])

    # 2. backup.py
    replacements_backup = [
        ('f"✅ اكتمل النسخ الاحتياطي الكامل بنجاح: {result[\'message\']}"', 'BACKUP_SUCCESS_FULL.format(message=result["message"])'),
        ('f"📁 تم تحميل {len(downloaded)} ملف محلياً"', 'BACKUP_DOWNLOADED_LOCAL.format(count=len(downloaded))'),
        ('"⚠️ الملفات لا تزال على الراوتر فقط"', 'BACKUP_ONLY_ON_ROUTER'),
        ('f"❌ فشل النسخ الاحتياطي: {result[\'message\']}"', 'BACKUP_FAILED_FULL.format(message=result["message"])'),
        ('f"✅ اكتمل النسخ الاحتياطي لـ User Manager بنجاح: {result[\'message\']}"', 'BACKUP_SUCCESS_USERMAN.format(message=result["message"])'),
        ('f"❌ فشل النسخ لـ User Manager: {result[\'message\']}"', 'BACKUP_FAILED_USERMAN.format(message=result["message"])'),
        ('f"❌ حدث خطأ غير متوقع أثناء النسخ الاحتياطي في الخلفية للراوتر {router_key}."', 'BACKUP_ERROR_UNEXPECTED.format(router_key=router_key)'),
        ('"⚠️ توجد عملية نسخ احتياطي جارية حالياً لهذا الراوتر. الرجاء الانتظار حتى تكتمل."', 'BACKUP_ALREADY_IN_PROGRESS'),
        ('f"{BACKUP_FULL_IN_PROGRESS}\\n\\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء."', 'BACKUP_BACKGROUND_NOTIFY.format(msg=BACKUP_FULL_IN_PROGRESS)'),
        ('f"{BACKUP_USERMAN_IN_PROGRESS}\\n\\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء."', 'BACKUP_BACKGROUND_NOTIFY.format(msg=BACKUP_USERMAN_IN_PROGRESS)'),
        ('"⚠️ رابط تحميل غير صالح"', 'BACKUP_DL_INVALID_LINK'),
        ('"⚠️ نوع باكوب غير معروف"', 'BACKUP_DL_UNKNOWN_TYPE'),
        ('"⚠️ الملف غير موجود محلياً"', 'BACKUP_DL_NOT_LOCAL'),
        ('"⚠️ الملف كبير جداً للإرسال عبر تليجرام (أكبر من 50MB)"', 'BACKUP_DL_TOO_LARGE'),
        ('"❌ فشل إرسال الملف"', 'BACKUP_DL_SEND_FAIL'),
        ('"✅ تم إرسال الملف"', 'BACKUP_DL_SEND_SUCCESS')
    ]
    if replace_in_file("bot/handlers/backup.py", replacements_backup):
        add_imports("bot/handlers/backup.py", ["BACKUP_SUCCESS_FULL", "BACKUP_DOWNLOADED_LOCAL", "BACKUP_ONLY_ON_ROUTER", "BACKUP_FAILED_FULL", "BACKUP_SUCCESS_USERMAN", "BACKUP_FAILED_USERMAN", "BACKUP_ERROR_UNEXPECTED", "BACKUP_ALREADY_IN_PROGRESS", "BACKUP_BACKGROUND_NOTIFY", "BACKUP_DL_INVALID_LINK", "BACKUP_DL_UNKNOWN_TYPE", "BACKUP_DL_NOT_LOCAL", "BACKUP_DL_TOO_LARGE", "BACKUP_DL_SEND_FAIL", "BACKUP_DL_SEND_SUCCESS"])

    # 3. audit.py
    replacements_audit = [
        ('"router": "🔍 اختر الراوتر"', '"router": AUDIT_SUBMENU_ROUTER'),
        ('"admin": "👤 اختر المشرف"', '"admin": AUDIT_SUBMENU_ADMIN'),
        ('"action": "⚙️ اختر العملية"', '"action": AUDIT_SUBMENU_ACTION'),
        ('"time": "🕓 اختر المدة"', '"time": AUDIT_SUBMENU_TIME'),
        ('"بدون فلاتر"', 'AUDIT_NO_FILTERS'),
        ('"اختر"', 'AUDIT_SUBMENU_CHOOSE'),
        ('f"{title}\\n\\n🔢 العدد: {len(options)}"', 'AUDIT_SUBMENU_COUNT.format(title=title, count=len(options))'),
        ('f"📋 سجل التدقيق\\n\\n{header}\\n\\n{NO_RESULTS}"', 'AUDIT_LIST_EMPTY.format(header=header, no_results=NO_RESULTS)'),
        ('f"📋 سجل التدقيق\\n\\n{header}\\n\\n📭 لا توجد سجلات في هذه الصفحة"', 'AUDIT_PAGE_EMPTY.format(header=header)'),
        ('f"📋 \u003cb\u003eسجل التدقيق\u003c/b\u003e ({start}-{end} من {total})"', 'AUDIT_LIST_HEADER.format(start=start, end=end, total=total)')
    ]
    if replace_in_file("bot/handlers/audit.py", replacements_audit):
        add_imports("bot/handlers/audit.py", ["AUDIT_SUBMENU_ROUTER", "AUDIT_SUBMENU_ADMIN", "AUDIT_SUBMENU_ACTION", "AUDIT_SUBMENU_TIME", "AUDIT_NO_FILTERS", "AUDIT_SUBMENU_CHOOSE", "AUDIT_SUBMENU_COUNT", "AUDIT_LIST_EMPTY", "AUDIT_PAGE_EMPTY", "AUDIT_LIST_HEADER"])

do_replacements()
print("Replacements for batch 2 done.")
