import os

messages_file = "bot/messages.py"
with open(messages_file, "a", encoding="utf-8") as f:
    f.write("""
# ─── BACKUP AND RESTORE STRINGS ────────────────────────────────
BACKUP_RESTORE_INVALID_NAME = "اسم ملف الاستعادة غير صالح"
BACKUP_RESTORE_NOT_FOUND = "الملف غير موجود"
BACKUP_RESTORE_PROFILES_COUNT = "📋 {count} بروفايل"
BACKUP_RESTORE_USERS_COUNT = "👥 {count} مستخدم"
BACKUP_RESTORE_SKIPPED = "⏭️ {skipped} تم تخطيها"
BACKUP_RESTORE_NONE = "لا شيء"
BACKUP_SUCCESS_FULL = "✅ اكتمل النسخ الاحتياطي الكامل بنجاح: {message}"
BACKUP_DOWNLOADED_LOCAL = "📁 تم تحميل {count} ملف محلياً"
BACKUP_ONLY_ON_ROUTER = "⚠️ الملفات لا تزال على الراوتر فقط"
BACKUP_FAILED_FULL = "❌ فشل النسخ الاحتياطي: {message}"
BACKUP_SUCCESS_USERMAN = "✅ اكتمل النسخ الاحتياطي لـ User Manager بنجاح: {message}"
BACKUP_FAILED_USERMAN = "❌ فشل النسخ لـ User Manager: {message}"
BACKUP_ERROR_UNEXPECTED = "❌ حدث خطأ غير متوقع أثناء النسخ الاحتياطي في الخلفية للراوتر {router_key}."
BACKUP_ALREADY_IN_PROGRESS = "⚠️ توجد عملية نسخ احتياطي جارية حالياً لهذا الراوتر. الرجاء الانتظار حتى تكتمل."
BACKUP_BACKGROUND_NOTIFY = "{msg}\\n\\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء."
BACKUP_DL_INVALID_LINK = "⚠️ رابط تحميل غير صالح"
BACKUP_DL_UNKNOWN_TYPE = "⚠️ نوع باكوب غير معروف"
BACKUP_DL_NOT_LOCAL = "⚠️ الملف غير موجود محلياً"
BACKUP_DL_TOO_LARGE = "⚠️ الملف كبير جداً للإرسال عبر تليجرام (أكبر من 50MB)"
BACKUP_DL_SEND_FAIL = "❌ فشل إرسال الملف"
BACKUP_DL_SEND_SUCCESS = "✅ تم إرسال الملف"

# ─── AUDIT STRINGS ──────────────────────────────────────────────
AUDIT_SUBMENU_ROUTER = "🔍 اختر الراوتر"
AUDIT_SUBMENU_ADMIN = "👤 اختر المشرف"
AUDIT_SUBMENU_ACTION = "⚙️ اختر العملية"
AUDIT_SUBMENU_TIME = "🕓 اختر المدة"
AUDIT_NO_FILTERS = "بدون فلاتر"
AUDIT_SUBMENU_CHOOSE = "اختر"
AUDIT_SUBMENU_COUNT = "{title}\\n\\n🔢 العدد: {count}"
AUDIT_LIST_EMPTY = "📋 سجل التدقيق\\n\\n{header}\\n\\n{no_results}"
AUDIT_PAGE_EMPTY = "📋 سجل التدقيق\\n\\n{header}\\n\\n📭 لا توجد سجلات في هذه الصفحة"
AUDIT_LIST_HEADER = "📋 <b>سجل التدقيق</b> ({start}-{end} من {total})"
""")
print("Appended strings to messages.py")
