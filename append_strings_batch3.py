import os

messages_file = "bot/messages.py"
with open(messages_file, "a", encoding="utf-8") as f:
    f.write("""
# ─── WATCHDOG STRINGS ──────────────────────────────────────────
WATCHDOG_QUEUE_UNAVAILABLE = "❌ Job Queue غير متاح"
WATCHDOG_ALREADY_RUNNING = "✅ مراقبة الراوترات تعمل بالفعل"
WATCHDOG_STARTED = "✅ تم بدء مراقبة الراوترات (كل 5 دقائق)"
WATCHDOG_STOPPED = "❌ تم إيقاف مراقبة الراوترات"
WATCHDOG_NO_ROUTERS = "📭 لا توجد روترات محفوظة"
WATCHDOG_STATUS_HEADER = "📊 <b>حالة الراوترات:</b>\\n"
WATCHDOG_LAST_OK = "آخر اتصال: {date}"
WATCHDOG_ONLINE = "متصل"
WATCHDOG_LAST_FAIL = "آخر فشل: {date}"
WATCHDOG_NOT_CHECKED = "لم يتم الفحص بعد"
WATCHDOG_VERSION = "   ├─ الإصدار: {version}"
WATCHDOG_ACTIVE_HOTSPOT = "   ├─ مستخدمو Hotspot النشطون: {count}"
WATCHDOG_LAST_BACKUP = "   └─ آخر نسخة احتياطية: {backup}\\n"
WATCHDOG_REFRESH_BTN = "🔄 تحديث فوري (Live Ping)"
WATCHDOG_BACK_BTN = "🔙 رجوع"
WATCHDOG_REFRESHING = "⏳ جاري الفحص الحي للراوترات..."
WATCHDOG_OFFLINE_ALERT = "🔴 الروتر <b>{identity}</b> غير متصل!"
WATCHDOG_ONLINE_ALERT = "🟢 الروتر <b>{identity}</b> عاد للاتصال"

# ─── USERMAN SEARCH STRINGS ────────────────────────────────────
USERMAN_SEARCH_OFFLINE = " [🔴 معطل]"
USERMAN_SEARCH_FOUND = "🔍 تم العثور على {count}"
USERMAN_SEARCH_LIMIT = " — يعرض أول {limit}:"
USERMAN_SEARCH_STATUS_OFF = "🔴 معطل"
USERMAN_SEARCH_STATUS_ON = "🟢 نشط"
USERMAN_SEARCH_RESULT = "👤 مستخدم User Manager:\\n📛 الاسم: {name}\\n🔑 الرمز: {pwd}\\n📋 البروفايل: {profile}\\nوضع الحساب: {status}"
USERMAN_SEARCH_LOADING = "جاري البحث..."
USERMAN_SEARCH_SESSION_EXPIRED = "⚠️ انتهت الجلسة أو بيانات غير صالحة."
USERMAN_SEARCH_KICKED = "✅ تم طرد {killed} جلسة للمستخدم {username}."
USERMAN_SEARCH_RESET = "✅ تم تصفير عداد المستخدم {username}."
USERMAN_SEARCH_ENABLED = "✅ تم تفعيل المستخدم {username}."
USERMAN_SEARCH_DISABLED = "🔴 تم تعطيل المستخدم {username}."
USERMAN_SEARCH_DELETED = "🗑️ تم حذف المستخدم {username}."
USERMAN_SEARCH_ERROR = "❌ خطأ: {e}"
USERMAN_SEARCH_UNKNOWN_ERR = "غير معروف"

# ─── USERMAN STRINGS ───────────────────────────────────────────
USERMAN_PAYMENT_UNSPECIFIED = "غير محدد"
USERMAN_UNLINKED_WARNING = "\\n\\n⚠️ {unlinked} من {total} كارتاً لم يُربط بها البروفايل "

# ─── USAGE STRINGS ─────────────────────────────────────────────
USAGE_NO_ROUTER = "⚠️ لم يتم اختيار روتر"
USAGE_STATUS = "الحالة: {status}"

# ─── TIMEOUT STRINGS ───────────────────────────────────────────
TIMEOUT_MINS_5 = "5 دقائق"
TIMEOUT_MINS_15 = "15 دقيقة"
TIMEOUT_MINS_30 = "30 دقيقة"
TIMEOUT_MINS_60 = "60 دقيقة"
TIMEOUT_NO_LIMIT = "بدون إغلاق"
TIMEOUT_CANCEL_BTN = "❌ إلغاء"
TIMEOUT_HEADER = "⏰ <b>إعداد مدة الخمول (Session Timeout)</b>\\n\\nاختر المدة التي سيتم بعدها إغلاق الجلسة وإجبارك على اختيار الراوتر مجدداً (لحماية النظام):"
TIMEOUT_SAVED = "✅ تم حفظ إعداد الخمول بنجاح.\\nالمدة الحالية: "
TIMEOUT_SAVED_NO_LIMIT = "بدون إغلاق (مفتوح دائماً)."
TIMEOUT_SAVED_MINS = "{val} دقيقة."
TIMEOUT_SAVE_ERROR = "❌ حدث خطأ أثناء حفظ الإعداد."
""")
print("Appended strings to messages.py")
