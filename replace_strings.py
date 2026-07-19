import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)

    if new_content != content:
        # Check if we need to add imports for the constants
        new_constants = []
        for old, new in replacements:
            if new not in content: # VERY naive check
                # we just need to add the constants to the import from bot.messages
                const_name = new.split(' ')[0] if ' ' in new else new.split('.')[0] if '.' in new else new
                if const_name.isupper() and const_name.startswith('HOTSPOT_'):
                    new_constants.append(const_name)
                    
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

def do_replacements():
    # hotspot_search.py
    replacements_search = [
        ('"\\n    🔴 معطل"', 'HOTSPOT_SEARCH_OFFLINE'),
        ('f"🔍 تم العثور على {len(hosts)}"', 'HOTSPOT_SEARCH_FOUND.format(count=len(hosts))'),
        ('f" — يعرض أول {MAX_SEARCH_RESULTS}:"', 'HOTSPOT_SEARCH_LIMIT.format(limit=MAX_SEARCH_RESULTS)'),
        ('f"✅ تم طرد الجهاز «{host_name}» بنجاح"', 'HOTSPOT_KICK_SUCCESS_SINGLE.format(host_name=host_name)'),
        ('"❌ بيانات الحظر غير صالحة"', 'HOTSPOT_INVALID_BLOCK_DATA'),
        ('"❌ بيانات رفع الحظر غير صالحة"', 'HOTSPOT_INVALID_UNBLOCK_DATA')
    ]
    replace_in_file("bot/handlers/hotspot_search.py", replacements_search)
    
    # hotspot_edit.py
    replacements_edit = [
        ('f"🔄 تم طرد المستخدم من {len(kicked)} جهاز:\\n"', 'HOTSPOT_EDIT_KICK_COUNT.format(count=len(kicked))'),
        ('"✅ تم تصفير العدادات\\n"', 'HOTSPOT_EDIT_RESET_SUCCESS'),
        ('"فارغ"', 'HOTSPOT_EDIT_EMPTY_VALUE'),
        ('f"✏️ أرسل القيمة الجديدة للحقل «{field_names.get(field, field)}»:\\n"', 'HOTSPOT_EDIT_FIELD_PROMPT.format(field_name=field_names.get(field, field))'),
        ('f"📌 القيمة الحالية: <code>{current_value}</code>"', 'HOTSPOT_EDIT_CURRENT_VALUE.format(current_value=current_value)'),
        ('f"\\n🔄 تم طرد المستخدم من {len(kicked)} جهاز"', 'HOTSPOT_EDIT_KICK_COUNT_INLINE.format(count=len(kicked))'),
        ('f"✅ تم التعديل بنجاح{kick_msg}\\n\\n"', 'HOTSPOT_EDIT_SUCCESS.format(kick_msg=kick_msg)')
    ]
    replace_in_file("bot/handlers/hotspot_edit.py", replacements_edit)
    
    # hotspot_common.py
    replacements_common = [
        ('f"📋 تم العثور على {len(users)} مستخدم ({paginator.slice_info}):\\n\\nاختر المستخدم للحذف:"', 'HOTSPOT_PAGINATION_DELETE.format(count=len(users), slice_info=paginator.slice_info)'),
        ('f"📋 تم العثور على {len(users)} مستخدم ({paginator.slice_info}):\\n\\nاختر المستخدم للتعديل:"', 'HOTSPOT_PAGINATION_EDIT.format(count=len(users), slice_info=paginator.slice_info)')
    ]
    replace_in_file("bot/handlers/hotspot_common.py", replacements_common)

    # hotspot_add.py
    replacements_add = [
        ('f"{e}\\n\\n💡 أو اتركها فارغة للتخطي."', 'HOTSPOT_ADD_BYTES_HINT.format(error=e)'),
        ('"❌ قيمة غير صالحة. الرجاء إدخال رقم صحيح."', 'HOTSPOT_ADD_INVALID_UPTIME'),
        ('"❌ الرجاء استخدام الأزرار أدناه لاختيار نوع المدة أو التخطي."', 'HOTSPOT_ADD_USE_BUTTONS')
    ]
    replace_in_file("bot/handlers/hotspot_add.py", replacements_add)

do_replacements()
print("Replaced strings successfully.")
