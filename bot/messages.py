MAIN_MENU = """👤 {admin_name}{router_part}
🏠 القائمة الرئيسية

اختر الروتر ثم اختر العملية:"""

SELECT_ROUTER = "🌐 اختر الروتر:"

HOTSPOT_MENU = """👤 {admin_name}{router_part}
📡 إدارة Hotspot

اختر العملية:"""

USERMAN_MENU = """👤 {admin_name}{router_part}
🎫 إدارة User Manager

اختر العملية:"""

ADD_USER_PROMPT = "👤 أرسل اسم المستخدم:"

EDIT_USER_PROMPT = """✏️ تعديل مستخدم

أرسل اسم المستخدم أو جزء من التعليق للبحث:"""

EDIT_SELECT_FIELD = "✏️ اختر الحقل لتعديله:\n\n{}"

DELETE_USER_PROMPT = """🗑️ حذف مستخدم

أرسل اسم المستخدم أو جزء من التعليق للبحث:"""

SEARCH_PROMPT = """🔍 بحث عن الأجهزة

أرسل الـ MAC أو الـ IP:"""

USERMAN_SEARCH_PROMPT = """🔍 بحث عن مستخدم

أرسل اسم المستخدم (Username):"""
SEARCH_ADVANCED_HINT = """

مثال: mac:XX:XX:XX:XX:XX أو ip:192.168.1.1 أو user:اسم أو comment:تعليق"""

CARDS_PROMPT = """🎫 إنشاء كروت User Manager

اختر نوع الكروت:
1️⃣ اسم مستخدم + كلمة سر مختلفين
2️⃣ اسم مستخدم + كلمة سر متشابهين
3️⃣ اسم مستخدم + كلمة سر فارغة

ثم أرسل عدد الكروت"""

STATS_MENU = """👤 {admin_name}{router_part}
📊 الإحصائيات

اختر نوع الإحصائيات:"""

BACKUP_MENU = """👤 {admin_name}{router_part}
💾 نظام Backup

اختر نوع الباكوب:"""

PDF_SETTINGS_MENU = """⚙️ إعدادات PDF

اختر الإعداد لتعديله:"""

CANCELLED = "❌ تم الإلغاء"

SUCCESS_ADD = "✅ تم إضافة المستخدم بنجاح"
SUCCESS_EDIT = "✅ تم تعديل المستخدم بنجاح"
SUCCESS_DELETE = "✅ تم حذف المستخدم بنجاح"
TOGGLE_DISABLED_ON = "🟢 تم تفعيل المستخدم"
TOGGLE_DISABLED_OFF = "🔴 تم تعطيل المستخدم"
ERROR_OCCURRED = "❌ حدث خطأ: {}"
NO_RESULTS = "📭 لا توجد نتائج"
CONFIRM_DELETE = "⚠️ هل أنت متأكد من حذف المستخدم؟\n\n{}"

WELCOME = """👤 {admin_name}
👋 مرحباً بك في بوت إدارة ميكروتيك

اختر الروتر للبدء:"""

NO_ROUTER_SELECTED = "⚠️ لم يتم اختيار روتر بعد!\n\nاختر روتر من القائمة أو اكتشف روترات جديدة."

DISCOVERY_START = "⏳ جاري البحث عن روترات ميكروتيك على الشبكة..."
DISCOVERY_RESULTS = "📡 تم العثور على {} روتر:\n\n{}"
DISCOVERY_NO_RESULTS = "📭 لم يتم العثور على أي روترات ميكروتيك على الشبكة المحلية\n\nتأكد من:\n1. البوت يعمل بصلاحيات Administrator\n2. الروتر متصل بنفس الشبكة\n3. الفايرول يسمح بالبورت 8728"
DISCOVERY_PERMISSION_ERROR = "⚠️ خطأ صلاحيات!\n\nاكتشاف الم.ndp يتطلب صلاحيات Administrator على Windows.\n\n🔧 الحل:\n- أغلق البوت وأعد تشغيله كـ Administrator\n- أو نفّذ الأمر: python main.py من موجه أوامر مُشغَّل بصلاحيات مسؤول"
ROUTER_ALREADY_EXISTS = "⚠️ هذا الروتر مسجل مسبقاً بعنوان {ip}.\nالاسم الحالي: {name}\n\n"
DISCOVERY_CREDENTIALS = "👤 أدخل يوزر الروتر {}:"
DISCOVERY_PASSWORD = "🔑 أدخل باسورد الروتر {}:"
DISCOVERY_CONNECTING = "⏳ جاري الاتصال بـ {}..."
DISCOVERY_SUCCESS = "✅ تم الاتصال والحفظ بنجاح!\n\n🌐 {}\n📋 الإصدار: {}\n🔧 {}\n\nيمكنك الآن إدارة هذا الروتر."
ROUTER_UPDATED = "✅ تم تحديث بيانات الروتر بنجاح!\n\n🌐 {}\n📋 الإصدار: {}\n📍 {}"
DISCOVERY_FAILED = "❌ فشل الاتصال. تأكد من:\n1. تفعيل API Service في WinBox (IP > Services > api)\n2. صحة اليوزر والباسورد\n3. البورت 8728 مفتوح في الفايرول"
SAVED_ROUTERS = "📋 الروترات المحفوظة:\n\n{}"
SAVED_ROUTERS_EMPTY = "📭 لا توجد روترات محفوظة\n\nاستخدم 🔍 اكتشاف روترات جديدة للبحث"
SAVED_ROUTER_OFFLINE = "🔴 {} - {} (غير متصل)"
SAVED_ROUTER_ONLINE = "🟢 {} - {} (متصل)"
DELETE_ROUTER_CONFIRM = "⚠️ هل أنت متأكد من حذف الروتر {}؟"
ROUTER_DELETED = "✅ تم حذف الروتر"
REFRESHING_ROUTERS = "🔄 جاري تحديث حالة الروترات المحفوظة..."

REBOOT_CONFIRM = "⚠️ هل أنت متأكد من إعادة تشغيل الروتر {}؟\n\n⛔ سيتم فصل جميع المستخدمين!"
REBOOT_IN_PROGRESS = "⏳ جاري إعادة تشغيل الروتر..."
REBOOT_SUCCESS = "✅ تم إعادة تشغيل الروتر بنجاح"
REBOOT_FAILED = "❌ فشل إعادة التشغيل: {}"
REBOOT_CANCELLED = "❌ تم إلغاء إعادة التشغيل"
NO_REBOOT_ROUTER = "⚠️ لم يتم اختيار روتر بعد!"

SCHEDULE_MENU = """⏰ نظام الباكوب الآلي

الحالة: {status}
{time_line}
📌 النطاق: جميع الراوترات المحفوظة التي لها بيانات اتصال — نسخ User Manager يومياً لكل منها.

اختر العملية:"""
SCHEDULE_TIME_LINE = "⏱ الوقت: {hour:02d}:{minute:02d}"
SCHEDULE_TIME_LINE_EMPTY = ""
SCHEDULE_ENABLED = "🟢 مفعل"
SCHEDULE_DISABLED = "🔴 معطل"
SCHEDULE_TIME_PROMPT = "⏰ أرسل وقت الباكوب اليومي (مثال: 03:00):"
SCHEDULE_SET = "✅ تم ضبط الباكوب الآلي"
SCHEDULE_REMOVED = "❌ تم إلغاء الباكوب الآلي"
SCHEDULE_ERROR = "❌ فشل: {}"
DUPLICATE_USER = "❌ هذا الاسم موجود مسبقاً، اختر اسماً آخر"
CLEAN_DONE = "✅ تم تنظيف الشات"
SYNC_COMMANDS_DONE = "✅ تم تحديث قائمة الأوامر السريعة"

METRICS_HEADER = "📊 <b>أداء الاتصال</b>\n"
METRICS_ACTIVE = "🔌 الاتصالات النشطة: {active}"
METRICS_STALE = "🗑️ الاتصالات القديمة المغلقة: {stale}"
METRICS_TOTAL = "🔁 إجمالي المحاولات: {total}"
METRICS_SUCCESS = "✅ الناجحة: {success}"
METRICS_FAILED = "❌ الفاشلة: {failed}"
METRICS_CACHE = "💾 استخدام الكاش: {cache_hits}"

HELP = """👋 <b>مرحباً بك في بوت إدارة ميكروتيك</b>

<b>الأوامر المتاحة:</b>
/start - 🏠 بدء البوت والعودة للقائمة الرئيسية
/help - ℹ️ عرض رسالة المساعدة هذه
/add - ➕ إضافة مستخدم Hotspot
/edit - ✏️ تعديل مستخدم Hotspot
/delete - 🗑️ حذف مستخدم Hotspot
/search - 🔍 بحث عن جهاز في Hotspot
/cards - 🎫 إنشاء كروت Hotspot
/userman - 🎫 إدارة User Manager
/backup - 📦 النسخ الاحتياطي
/routers - 🌐 إدارة الروترات
/addrouter - 🌐 إضافة روتر يدوياً
/settings - ⚙️ إعدادات PDF
/reboot - 🔄 إعادة تشغيل الراوتر
/metrics - 📊 أداء الاتصال
/logs - 📋 سجل التدقيق
/sync - 🔄 تحديث قائمة الأوامر
/clean - 🧹 تنظيف الشات
/usage - 📊 تقرير استخدام مستخدم
/watchdog - 🔍 حالة الروترات
/watchdog_start - 🟢 بدء مراقبة الروترات
/cancel - ❌ إلغاء العملية

<b>القوائم الرئيسية:</b>
• 📡 <b>Hotspot</b> - إضافة، تعديل، حذف، بحث، عرض المستخدمين
• 🎫 <b>User Manager</b> - إنشاء كروت، عرض المستخدمين، جلب البروفايلات
• 📊 <b>الإحصائيات</b> - إحصائيات Hotspot و User Manager
• 💾 <b>Backup</b> - نسخ احتياطي يدوي وتلقائي
• ⚙️ <b>إعدادات PDF</b> - تعديل إعدادات طباعة الكروت

<b>ملاحظات:</b>
• يجب اختيار روتر أولاً قبل تنفيذ أي عملية
• للعودة للقائمة الرئيسية من أي شاشة استخدم 🏠 الرئيسية
• الأزرار الزرقاء هي للتنقل، والحمراء للإلغاء"""

# ─── COMMON ────────────────────────────────────────────────────────────

CMD_START_DESC = "🏠 القائمة الرئيسية"
CMD_HELP_DESC = "❓ مساعدة"
CMD_REBOOT_DESC = "🔄 اعادة تشغيل الراوتر"
CMD_ADD_DESC = "➕ اضافة مستخدم هوت سبوت"
CMD_DELETE_DESC = "🗑️ حذف مستخدم هوت سبوت"
CMD_SEARCH_DESC = "🔍 بحث عن مستخدم"
CMD_CARDS_DESC = "🎫 إنشاء كروت هوت سبوت"
CMD_USERMAN_DESC = "🎫 إدارة User Manager"
CMD_BACKUP_DESC = "📦 الباكوب"
CMD_ROUTERS_DESC = "🌐 إدارة الروترات"
CMD_SETTINGS_DESC = "⚙️ الإعدادات"
CMD_CANCEL_DESC = "❌ الغاء العملية"
CMD_CLEAN_DESC = "🧹 تنظيف الشات"
CMD_USAGE_DESC = "📊 تقرير استخدام مستخدم"
CMD_WATCHDOG_DESC = "🔍 حالة الروترات"
CMD_WATCHDOG_START_DESC = "🟢 بدء مراقبة الروترات"
CMD_METRICS_DESC = "📊 أداء الاتصال"
CMD_SYNC_DESC = "🔄 تحديث قائمة الأوامر"

# ─── SHARED ────────────────────────────────────────────────────────────

UNKNOWN_NAME = "غير معروف"

# ─── HOTSPOT ───────────────────────────────────────────────────────────

USER_NOT_FOUND = "❌ المستخدم غير موجود"
SEARCHING_HOSTS = "🔍 جاري البحث في الأجهزة..."
INVALID_SELECTION = "❌ اختيار غير صالح"
INVALID_PROFILE = "بروفايل غير صالح"
DEVICE_NOT_SELECTED = "❌ لم يتم تحديد جهاز"
DEVICE_NOT_FOUND = "❌ الجهاز غير موجود"
HOST_KICK_FAILED = "❌ فشل طرد الجهاز"
USER_NOT_SELECTED = "❌ لم يتم تحديد مستخدم"
NO_ACTIVE_DEVICES = "✅ لا توجد أجهزة نشطة"
NO_ACTIVE_DEVICES_FOR_USER = "ℹ️ لا توجد أجهزة نشطة لهذا المستخدم لطردها"
CHOOSE_NEW_PROFILE = "📋 اختر البروفايل الجديد:"
DATA_ERROR = "❌ خطأ في البيانات"
SEND_PASSWORD = "🔑 أرسل الباسورد:"
CHOOSE_PROFILE_OR_TYPE = "📋 اختر البروفايل أو اكتب اسمه:"
SEND_BYTES_LIMIT = "📊 أرسل الحد الكلى (مثال: 1G, 500M) أو تخطي:"
SEND_COMMENT_OR_SKIP = "💬 أرسل التعليق (أو تخطي):"
SEND_PROFILE_NAME = "📋 أرسل اسم البروفايل:"
SEND_BYTES_LIMIT_SHORT = "📊 أرسل الحد الكلى:"
CHOOSE_PROFILE = "📋 اختر البروفايل:"
SEND_COMMENT = "💬 أرسل التعليق:"
INCOMPLETE_DATA = "❌ بيانات غير مكتملة"

SEND_UPTIME_TYPE = "⏰ اختر نوع مدة الصلاحية:"
SEND_UPTIME_HOURS = "⏰ أرسل عدد الساعات (مثال: 24, 48, 72):"
SEND_UPTIME_DAYS = "📅 أرسل عدد الأيام (مثال: 1, 7, 30):"
SEND_UPTIME_SHORT = "⏰ أرسل مدة الصلاحية:"

EDIT_FIELD_NAMES = {
    "name": "الاسم",
    "password": "الباسورد",
    "profile": "البروفايل",
    "bytes": "الحد الكلى",
    "uptime": "مدة الصلاحية",
    "comment": "التعليق",
}

ENTER_CARD_COUNT = "🎫 أرسل عدد الكروت:"
ENTER_CARD_LENGTH = "🔢 أرسل طول أرقام الكروت (3, 4, 5...):"
ENTER_CARD_PREFIX = "🏷️ أرسل البادئة (أو تخطي):"
CHOOSE_CARD_SYSTEM = "📋 اختر نظام الكروت:"
CHOOSE_CARD_PROFILE = "📋 اختر البروفايل للكروت:"
CARD_UPTIME_PROMPT = "⏰ أرسل مدة صلاحية الكروت (أو تخطي):"
CARD_BYTES_PROMPT = "📊 أرسل حد البيانات للكروت (مثال: 1G, 500M) أو تخطي:"
CARDS_CREATED = "✅ تم إنشاء {count} كارت بنجاح!"
CARDS_SAVED = "✅ تم حفظ ملف PDF بنجاح!"
PDF_READY = "📄 ملف PDF جاهز — أرسله لك"

# ─── ROUTERS ───────────────────────────────────────────────────────────

ROUTER_NOT_FOUND = "❌ الروتر غير موجود"
ERROR_TRY_AGAIN = "❌ حدث خطأ، حاول مرة أخرى"
ROUTER_NAME_EMPTY = "❌ الاسم لا يمكن أن يكون فارغاً"
ROUTER_NO_CREDENTIALS = "❌ الروتر ليس لديه بيانات اتصال. احذفه وأعد الاكتشاف."

# Manual router add flow
MANUAL_ADD_IP_PROMPT = "🌐 أدخل عنوان IP للروتر الجديد:"
MANUAL_ADD_PORT_PROMPT = "🔌 أدخل المنفذ (اتركه فارغاً للافتراضي {}):"
MANUAL_ADD_USER_PROMPT = "👤 أدخل اسم المستخدم (username):"
MANUAL_ADD_PASS_PROMPT = "🔑 أدخل كلمة المرور:"
MANUAL_ADD_ALIAS_PROMPT = "🏷️ أدخل اسماً مستعاراً اختيارياً (أرسل /skip للتخطي):"
MANUAL_ADD_CONFIRM = "تأكيد إضافة الروتر:\n\n📍 IP: {}\n🔌 المنفذ: {}\n👤 المستخدم: {}\n🏷️ الاسم: {}"
MANUAL_ADD_DUPLICATE = "⚠️ الروتر {} مسجل مسبقاً ({})"
MANUAL_ADD_SAVED = "✅ تم حفظ الروتر {}\n📍 {}"
MANUAL_ADD_CONN_FAILED = "✅ تم الحفظ، لكن تعذّر الاتصال للتحقق:\n{}\n📍 الروتر محفوظ بياناته."
MANUAL_ADD_INVALID = "❌ {}"

# ─── USERMAN ───────────────────────────────────────────────────────────

NO_PROFILES_AVAILABLE = "❌ لا توجد بروفايلات. تأكد من الاتصال بالروتر."

USERMAN_ADD_PROFILE_PROMPT = "📦 اختر الباقة (البروفايل) لإضافتها للمستخدم:"
USERMAN_ADD_PROFILE_SUCCESS = "✅ تمت إضافة الباقة «{profile}» للمستخدم {username}."
USERMAN_ADD_PROFILE_FAILED = "❌ فشل إضافة الباقة «{profile}» للمستخدم {username}: {error}"
USERMAN_NO_PROFILES_TO_ADD = "📭 لا توجد بروفايلات متاحة لإضافتها على هذا الروتر."
SEND_CARD_COUNT = "🔢 أرسل عدد الكروت:"
MAX_CARDS_EXCEEDED = "❌ الحد الأقصى 100 كارت"
CREATING_CARDS = "⏳ جاري إنشاء الكروت..."
PDF_FILE_CAPTION = "📄 ملف PDF للكروت"
PROFILES_HEADER = "📋 البروفايلات:\n"
NO_PROFILES = "📭 لا توجد بروفايلات"

CHOOSE_PAYMENT = "💰 اختر حالة الدفع للكروت:"
PAYMENT_PAID = "مدفوع"
PAYMENT_UNPAID = "غير مدفوع"

CHOOSE_MAC_BIND = """🔗 ربط الكروت بعنوان MAC (caller-id)؟

• «ربط بجهاز معروف»: أدخل MAC واحداً مسبقاً ويُطبَّق على كل الكروت.
• «بدون ربط»: اترك الحساب دون تقييد بأي جهاز."""
MAC_PROMPT = "📡 أرسل عنوان MAC للربط (مثل AA:BB:CC:DD:EE:FF):"
INVALID_MAC = "❌ عنوان MAC غير صالح. أرسل صيغة صحيحة مثل AA:BB:CC:DD:EE:FF"
CARDS_CREATED_DETAIL = "✅ تم إنشاء {count} كارت بنجاح!\n📅 {created_at}\n💰 الدفع: {payment}"

# ─── BACKUP ────────────────────────────────────────────────────────────

BACKUP_FULL_IN_PROGRESS = "⏳ جاري عمل Full System Backup..."
BACKUP_USERMAN_IN_PROGRESS = "⏳ جاري عمل User Manager Backup..."
BACKUP_RESTORE_AVAILABLE = "📦 النسخ الاحتياطية المتاحة ({count}):\n\nاختر النسخة للاستعادة:"
BACKUP_RESTORE_CONFIRM = "⚠️ هل أنت متأكد من استعادة النسخة الاحتياطية؟\n\n📦 {name}\n\n⛔ سيؤدي هذا إلى إعادة تشغيل الروتر!"
BACKUP_RESTORE_IN_PROGRESS = "⏳ جاري استعادة النسخة الاحتياطية {name}..."
BACKUP_RESTORE_SUCCESS = "✅ تمت استعادة النسخة الاحتياطية {name} بنجاح"
BACKUP_RESTORE_FAILED = "❌ فشل الاستعادة: {error}"
BACKUP_RESTORE_NO_BACKUPS = "📭 لا توجد نسخ احتياطية على هذا الروتر"
INVALID_TIME_FORMAT = "صيغة غير صحيحة. استخدم HH:MM (مثال: 03:00)"

# ─── PDF SETTINGS ──────────────────────────────────────────────────────

PDF_MARGINS_PROMPT = "📏 الهوامش الحالية:\nأعلى={top} | أسفل={bottom} | يسار={left} | يمين={right}\n\nأرسل القيمة الجديدة بالترتيب: أعلى أسفل يسار يمين"
PDF_CARD_SIZE_PROMPT = "📐 حجم الكارت الحالي: {width} × {height} مم\n\nأرسل العرض والارتفاع بالمم"
PDF_SPACING_PROMPT = "↔️ الفواصل الحالية: أفقي={x} | عمودي={y} مم\n\nأرسل الفواصل الجديدة: أفقي عمودي"
PDF_CARDS_PER_ROW_PROMPT = "📄 الكروت في الصف الحالي: {value}\n\nأرسل العدد الجديد"
PDF_CARDS_PER_PAGE_PROMPT = "📄 الكروت في الصفحة الحالية: {value}\n\nأرسل العدد الجديد"
PDF_BRAND_NAME_PROMPT = "🏷️ اسم الشبكة الحالي: {value}\n\nأرسل الاسم الجديد:"
PDF_HOTSPOT_DNS_PROMPT = "🌐 IP أو DNS للـ Hotspot الحالي: {value}\n\n📌 أدخل فقط IP أو العنوان\nالرابط الكامل: http://{{IP}}/login?username=...&password=...\n\nمثال: 192.0.0.1 أو hotspot.mynetwork.com"
PDF_SHOW_QR_PROMPT = "📱 QR Code الحالي: {value}\n\n1️⃣ تفعيل\n2️⃣ تعطيل"
PDF_FOOTER_PROMPT = "📝 التذييل الحالي: {value}\n\nأرسل نص التذييل الجديد:"
PDF_LABEL_SPACING_PROMPT = "📐 تباعد النصوص الحالي:\nرقم الشحن: {single}\nاليوزر/الباسورد: {dual}\n\n📌 القيمة 1.0 = التخطيط الحالي\n📌 القيمة 1.5 = المسافة تزيد 50%\n📌 القيمة 0.5 = المسافة تنقص 50%\n\nأرسل القيمتين مفصولتين بمسافة:\nتباعد رقم الشحن تباعد اليوزر/الباسورد"
PDF_VALUE_FONT_SIZE_PROMPT = "🔤 أحجام الخط الحالية:\nرقم شحن (أقصى): {single}\nيوزر/باسورد (أقصى): {dual}\n\n📌 النطاق المسموح: 8-16\n📌 الحد الأدنى ثابت = 7 دائماً\n\nأرسل القيمتين مفصولتين بمسافة:\nحجم_أقصى_رقم_شحن حجم_أقصى_يوزر/باسورد"
PDF_BORDER_PROMPT = "📏 سمك الحدود الحالي: {value} مم\n\nأرسل القيمة الجديدة (رقم):"
PDF_UNKNOWN_OPTION = "❌ خيار غير معروف"
PDF_SEND_4_VALUES = "❌ أرسل 4 قيم مفصولين بمسافات"
PDF_SEND_2_VALUES = "❌ أرسل قيمتين مفصولتين بمسافة"
PDF_SETTINGS_UPDATED = "✅ تم تحديث الإعدادات"


# ─── PHASE 1: USAGE ──────────────────────────────────────────

USAGE_PROMPT = '📊 <b>تقرير استخدام المستخدم</b>\n\nأرسل اسم المستخدم للبحث:'

USAGE_HEADER = '📊 <b>تقرير استخدام {username}</b>\n'
USAGE_STATUS_ACTIVE = '🟢 نشط'
USAGE_STATUS_DISABLED = '🔴 معطل'
USAGE_SERVER = '🖥️ السيرفر: {server}'
USAGE_PROFILE_LABEL = '📋 البروفايل: {profile}'
USAGE_PASSWORD_LABEL = '🔑 الباسورد: <code>{password}</code>'
USAGE_COMMENT_LABEL = '💬 التعليق: {comment}'
USAGE_BYTES_IN = '📥 وارد: {bytes}'
USAGE_BYTES_OUT = '📤 صادر: {bytes}'
USAGE_BYTES_TOTAL = '📊 الإجمالي: {bytes}'
USAGE_UPTIME_LABEL = '⏰ مدة الاتصال: {uptime}'
USAGE_CURRENT_ACTIVE = '<b>🔌 الأجهزة النشطة حالياً:</b>\n{devices}'
USAGE_DEVICE_LINE = '• {address} — {mac} — {uptime}'
USAGE_NO_ACTIVE = '📭 لا توجد أجهزة نشطة حالياً'
USAGE_LIMIT_LABEL = '📊 حد البيانات: {limit}'
USAGE_NO_LIMIT = 'غير محدود'


HOTSPOT_STATS =  """📊 إحصائيات Hotspot

👥 إجمالي المستخدمين: {total}
🟢 مفعل: {active}
🔴 معطّل: {inactive}
📦 توزيع الحد الكلى (للمستخدمين المفعلين):
<pre>
• 10 GB: {cat_10} مستخدم
• 20 GB: {cat_20} مستخدم
• 30 GB: {cat_30} مستخدم
• 40 GB: {cat_40} مستخدم
• 50 GB: {cat_50} مستخدم
• أخرى: {cat_other} مستخدم
</pre>"""

HOTSPOT_STATS_RESET_BLOCK = """🔄 تم تصفير العدادات في يوم ({selected_day}) — {reset_count} مستخدم:
<pre>
{reset_list}
</pre>"""

HOTSPOT_STATS_PROMPT = "📅 أدخل رقم اليوم (من الأيام المتاحة: {days}) لعرض المستخدمين الذين تم تصفير عداداتهم:"

HOTSPOT_STATS_DAY_INVALID = "❌ يرجى إدخال رقم يوم صحيح بين 1 و31."

HOTSPOT_STATS_DAY_NOT_FOUND = "⚠️ لا توجد سجلات تصفير لليوم {day}. الأيام المتاحة: {days}."

HOTSPOT_STATS_NO_RESET = "ℹ️ لا توجد سجلات تصفير عدادات حسب اليوم."


# ─── USERMAN RESTORE ───────────────────────────────────────────

USERMAN_RESTORE_MENU = "🎫 استعادة User Manager\n\nاختر ملف الاستعادة:"
USERMAN_RESTORE_NO_BACKUPS = "📭 لا توجد نسخ User Manager محفوظة"
USERMAN_RESTORE_CONFIRM = "⚠️ هل أنت متأكد من استعادة User Manager من الملف؟\n\n📦 {name}\n\n⛔ سيتم إعادة إنشاء المستخدمين والبروفايلات!"
USERMAN_RESTORE_IN_PROGRESS = "⏳ جاري استعادة User Manager..."
USERMAN_RESTORE_SUCCESS = "✅ تمت الاستعادة بنجاح:\n\n{summary}"
USERMAN_RESTORE_FAILED = "❌ فشل الاستعادة: {error}"
USERMAN_RESTORE_PARTIAL = "⚠️ تمت الاستعادة مع بعض الأخطاء:\n\n{summary}"


# ─── تنبيهات انتهاء الاشتراك ─────────────────────────────────
EXPIRY_ALERT_HEADER = "⏰ <b>تنبيه انتهاء الاشتراك — {router_name}</b>\n\nالمستخدمون التالية تنتهي صلاحيتهم خلال {days} أيام:\n"
EXPIRY_ALERT_USER_ROW = "• <b>{name}</b> | بروفايل: {profile} | متبقي: {remaining_days} يوم"
EXPIRY_ALERT_EMPTY = "✅ لا توجد اشتراكات منتهية خلال {days} أيام القادمة على {router_name}"

# ─── حظر MAC ──────────────────────────────────────────────────
BLOCK_MAC_SUCCESS = "🚫 تم حظر الجهاز <code>{mac}</code> بنجاح.\n\n⚠️ تأكد من وجود Firewall Rule تمنع address-list=hotspot_blocked من الاتصال."
BLOCK_MAC_FAIL = "❌ فشل حظر الجهاز. تحقق من الاتصال بالراوتر."
UNBLOCK_MAC_SUCCESS = "✅ تم رفع الحظر عن <code>{mac}</code>"
UNBLOCK_MAC_FAIL = "❌ فشل رفع الحظر. قد لا يكون الجهاز محظوراً."
BLOCKED_LIST_HEADER = "🚫 <b>الأجهزة المحظورة ({count}):</b>\n\nاضغط على جهاز لرفع حظره:"
BLOCKED_LIST_EMPTY = "✅ لا توجد أجهزة محظورة حالياً"

# ─── نظام الفواتير ─────────────────────────────────────────────
SALES_SUMMARY_HEADER = "💰 <b>ملخص المبيعات — آخر {days} يوم</b>\n\n"
SALES_SUMMARY_ROW = "📦 إجمالي الدفعات: {total_batches}\n✅ مدفوعة: {paid_count}\n🆓 غير مدفوعة: {unpaid_count}\n⏳ مرحّلة: {deferred_count}\n💵 الإيرادات: {total_revenue:.2f}"
MARK_PAID_SUCCESS = "✅ تم تحديث حالة الدفع إلى: {status_label}"
MARK_PAID_FAIL = "❌ فشل تحديث حالة الدفع"
PAYMENT_STATUS_LABELS = {"paid": "مدفوع ✅", "unpaid": "غير مدفوع 🆓", "deferred": "مرحّل ⏳"}

# ─── مشاركة كروت WiFi ─────────────────────────────────────────
SHARE_CARD_PROMPT = "📤 أرسل Telegram User ID للعميل الذي تريد إرسال الكرت إليه:\n\n💡 يمكنك إيجاد الـ ID عبر بوت @userinfobot"
SHARE_CARD_TEMPLATE = """📶 <b>بيانات اتصال WiFi</b>

👤 اسم المستخدم: <code>{username}</code>
🔑 كلمة المرور: <code>{password}</code>{dns_line}{ssid_line}

🎫 بروفايل: {profile}"""
SHARE_CARD_SUCCESS = "✅ تم إرسال بيانات الكرت للعميل بنجاح"
SHARE_CARD_FAIL = "❌ فشل الإرسال — تأكد من صحة الـ ID وأن العميل لم يحظر البوت"
SHARE_CARD_NO_CARDS = "⚠️ لا توجد كروت في هذه الدفعة"
SHARE_CARD_INVALID_ID = "❌ الـ ID غير صالح — أرسل رقماً صحيحاً"
