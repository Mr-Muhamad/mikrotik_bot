MAIN_MENU = """👤 {admin_name}{router_part}
🏠 القائمة الرئيسية

🔧 نظام الراوتر: {system_part}

اختر القسم:"""

ROUTER_SYSTEM_BOTH = "📡 هوتسبوت + 🎫 يوزر مانيجر"
ROUTER_SYSTEM_HOTSPOT = "📡 هوتسبوت فقط"
ROUTER_SYSTEM_USERMAN = "🎫 يوزر مانيجر فقط"
ROUTER_SYSTEM_UNKNOWN = "⚠️ غير محدد"

ROUTERS_MENU = """👤 {admin_name}{router_part}
🌐 إدارة الروترات

اختر العملية:"""

REPORTS_MENU = """👤 {admin_name}{router_part}
📈 التقارير والسجلات

اختر التقرير:"""

SELECT_ROUTER = "🌐 اختر الراوتر:"

HOTSPOT_MENU = """👤 {admin_name}{router_part}
📡 إدارة هوتسبوت

اختر العملية:"""

USERMAN_MENU = """👤 {admin_name}{router_part}
🎫 إدارة يوزر مانيجر

اختر العملية:"""

ADD_USER_PROMPT = "👤 أرسل اسم المستخدم:"

EDIT_USER_PROMPT = """✏️ تعديل
أرسل اسم المستخدم أو التعليق:"""

EDIT_SELECT_FIELD = "✏️ اختر الحقل:\n\n{}"

DELETE_USER_PROMPT = """🗑️ حذف
أرسل اسم المستخدم أو التعليق:"""

SEARCH_PROMPT = """🔍 بحث في الأجهزة
أرسل الـ MAC أو الـ IP:"""

USERMAN_SEARCH_PROMPT = """🔍 بحث عن مستخدم
أرسل اسم المستخدم (Username):"""
SEARCH_ADVANCED_HINT = """
مثال: mac:XX أو ip:1.1 أو user:اسم أو comment:تعليق"""

CARDS_PROMPT = """🎫 توليد كروت

اختر نوع الكروت المطلوبة:
1️⃣ اسم وكلمة سر مختلفين
2️⃣ اسم وكلمة سر متشابهين
3️⃣ اسم فقط (بدون كلمة سر)

ثم أرسل عدد الكروت"""

STATS_MENU = """👤 {admin_name}{router_part}
📊 الإحصائيات"""

BACKUP_MENU = """👤 {admin_name}{router_part}
💾 النسخ الاحتياطي"""

PDF_SETTINGS_MENU = """⚙️ إعدادات الطباعة
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
👋 أهلاً بك. اختر الراوتر للبدء:"""

NO_ROUTER_SELECTED = "⚠️ يجب عليك الاتصال براوتر أولاً قبل استخدام هذه القائمة أو الأوامر السريعة.\n\nيرجى اختيار راوتر لإدارته:"

DISCOVERY_START = "⏳ جاري البحث عن روترات ميكروتيك على الشبكة..."
DISCOVERY_RESULTS = "📡 تم العثور على {} روتر:\n\n{}"
DISCOVERY_NO_RESULTS = "📭 لم يتم العثور على أي روترات ميكروتيك على الشبكة المحلية\n\nتأكد من:\n1. البوت يعمل بصلاحيات Administrator\n2. الروتر متصل بنفس الشبكة\n3. الفايرول يسمح بالبورت 8728"
DISCOVERY_PERMISSION_ERROR = "⚠️ خطأ صلاحيات!\n\nاكتشاف الم.ndp يتطلب صلاحيات Administrator على Windows.\n\n🔧 الحل:\n- أغلق البوت وأعد تشغيله كـ Administrator\n- أو نفّذ الأمر: python main.py من موجه أوامر مُشغَّل بصلاحيات مسؤول"
ROUTER_ALREADY_EXISTS = (
    "⚠️ هذا الروتر مسجل مسبقاً بعنوان {ip}.\nالاسم الحالي: {name}\n\n"
)
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

REBOOT_CONFIRM = (
    "⚠️ هل أنت متأكد من إعادة تشغيل الراوتر {}؟\n⛔ سيتم فصل جميع المستخدمين!"
)
REBOOT_IN_PROGRESS = "⏳ جاري إعادة التشغيل..."
REBOOT_SUCCESS = "✅ تمت إعادة التشغيل بنجاح"
REBOOT_FAILED = "❌ فشل: {}"
REBOOT_CANCELLED = "❌ تم الإلغاء"
NO_REBOOT_ROUTER = "⚠️ اختر راوتر أولاً!"

SCHEDULE_MENU = """⏰ جدولة النسخ

الحالة: {status}
{time_line}
📌 النطاق: جميع الراوترات. نسخ احتياطي للنظام واليوزر مانيجر.

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

METRICS_SERVER_HEALTH = """
💻 <b>حالة السيرفر (System Health):</b>
- المعالج (CPU): {cpu}%
- الرام (RAM): {ram_used:.1f}GB / {ram_total:.1f}GB ({ram_percent}%)

🤖 <b>استهلاك البوت (Bot Footprint):</b>
- استهلاك الرام: {bot_ram:.1f} MB
- وقت التشغيل: {bot_uptime}"""

HELP = """👋 <b>مساعدة</b>

<b>الأوامر السريعة:</b>
/start - 🏠 القائمة الرئيسية
/add - ➕ إضافة هوتسبوت
/edit - ✏️ تعديل هوتسبوت
/delete - 🗑️ حذف هوتسبوت
/search - 🔍 بحث هوتسبوت
/cards - 🎫 توليد كروت
/userman - 🎫 يوزر مانيجر
/backup - 📦 نسخ احتياطي
/routers - 🌐 أجهزة الراوتر
/reboot - 🔄 إعادة التشغيل
/settings - ⚙️ إعدادات الطباعة
/clean - 🧹 مسح المحادثة
/cancel - ❌ إلغاء العملية
"""

# ─── COMMON ────────────────────────────────────────────────────────────

CMD_START_DESC = "🏠 الرئيسية"
CMD_HELP_DESC = "❓ مساعدة"
CMD_REBOOT_DESC = "🔄 إعادة تشغيل"
CMD_ADD_DESC = "➕ إضافة هوتسبوت"
CMD_DELETE_DESC = "🗑️ حذف هوتسبوت"
CMD_SEARCH_DESC = "🔍 بحث هوتسبوت"
CMD_CARDS_DESC = "🎫 كروت هوتسبوت"
CMD_USERMAN_DESC = "🎫 يوزر مانيجر"
CMD_BACKUP_DESC = "📦 النسخ الاحتياطي"
CMD_ROUTERS_DESC = "🌐 أجهزة الراوتر"
CMD_SETTINGS_DESC = "⚙️ إعدادات الطباعة"
CMD_CANCEL_DESC = "❌ إلغاء"
CMD_CLEAN_DESC = "🧹 مسح المحادثة"
CMD_USAGE_DESC = "📊 تقرير الاستخدام"
CMD_WATCHDOG_DESC = "🔍 حالة الروترات"
CMD_WATCHDOG_START_DESC = "🟢 بدء المراقبة"
CMD_METRICS_DESC = "📊 أداء الاتصال"
CMD_SYNC_DESC = "🔄 تحديث القائمة"

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
MANUAL_ADD_IP_PROMPT = "🌐 IP الراوتر الجديد:"
MANUAL_ADD_PORT_PROMPT = "🔌 المنفذ (فارغ للافتراضي {}):"
MANUAL_ADD_USER_PROMPT = "👤 اسم المستخدم (User):"
MANUAL_ADD_PASS_PROMPT = "🔑 كلمة المرور:"
MANUAL_ADD_ALIAS_PROMPT = "🏷️ الاسم المستعار (أو /skip):"
MANUAL_ADD_CONFIRM = "تأكيد الإضافة:\n📍 IP: {}\n🔌 Port: {}\n👤 User: {}\n🏷️ Name: {}"
MANUAL_ADD_DUPLICATE = "⚠️ الراوتر {} مسجل مسبقاً ({})"
MANUAL_ADD_SAVED = "✅ تم حفظ الراوتر {}\n📍 {}"
MANUAL_ADD_CONN_FAILED = (
    "✅ تم الحفظ، لكن تعذّر الاتصال للتحقق:\n{}\n📍 الروتر محفوظ بياناته."
)
MANUAL_ADD_INVALID = "❌ {}"

# ─── USERMAN ───────────────────────────────────────────────────────────

NO_PROFILES_AVAILABLE = "❌ لا توجد بروفايلات. تأكد من الاتصال بالروتر."

USERMAN_ADD_PROFILE_PROMPT = "📦 اختر الباقة (البروفايل) لإضافتها للمستخدم:"
USERMAN_ADD_PROFILE_SUCCESS = "✅ تمت إضافة الباقة «{profile}» للمستخدم {username}."
USERMAN_ADD_PROFILE_FAILED = (
    "❌ فشل إضافة الباقة «{profile}» للمستخدم {username}: {error}"
)
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
CARDS_CREATED_DETAIL = (
    "✅ تم إنشاء {count} كارت بنجاح!\n📅 {created_at}\n💰 الدفع: {payment}"
)

# ─── BACKUP ────────────────────────────────────────────────────────────

BACKUP_FULL_IN_PROGRESS = "⏳ جاري عمل Full System Backup..."
BACKUP_USERMAN_IN_PROGRESS = "⏳ جاري عمل User Manager Backup..."
BACKUP_RESTORE_AVAILABLE = (
    "📦 النسخ الاحتياطية المتاحة ({count}):\n\nاختر النسخة للاستعادة:"
)
BACKUP_RESTORE_CONFIRM = "⚠️ هل أنت متأكد من استعادة النسخة الاحتياطية؟\n\n📦 {name}\n\n⛔ سيؤدي هذا إلى إعادة تشغيل الروتر!"
BACKUP_RESTORE_IN_PROGRESS = "⏳ جاري استعادة النسخة الاحتياطية {name}..."
BACKUP_RESTORE_SUCCESS = "✅ تمت استعادة النسخة الاحتياطية {name} بنجاح"
BACKUP_RESTORE_FAILED = "❌ فشل الاستعادة: {error}"
BACKUP_RESTORE_NO_BACKUPS = "📭 لا توجد نسخ احتياطية على هذا الروتر"
INVALID_TIME_FORMAT = "صيغة غير صحيحة. استخدم HH:MM (مثال: 03:00)"

# ─── PDF SETTINGS ──────────────────────────────────────────────────────

PDF_MARGINS_PROMPT = "📏 الهوامش الحالية:\nأعلى={top} | أسفل={bottom} | يسار={left} | يمين={right}\n\nأرسل القيمة الجديدة بالترتيب: أعلى أسفل يسار يمين"
PDF_CARD_SIZE_PROMPT = (
    "📐 حجم الكارت الحالي: {width} × {height} مم\n\nأرسل العرض والارتفاع بالمم"
)
PDF_SPACING_PROMPT = (
    "↔️ الفواصل الحالية: أفقي={x} | عمودي={y} مم\n\nأرسل الفواصل الجديدة: أفقي عمودي"
)
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

USAGE_PROMPT = "📊 <b>تقرير استخدام المستخدم</b>\n\nأرسل اسم المستخدم للبحث:"

USAGE_HEADER = "📊 <b>تقرير استخدام {username}</b>\n"
USAGE_STATUS_ACTIVE = "🟢 نشط"
USAGE_STATUS_DISABLED = "🔴 معطل"
USAGE_SERVER = "🖥️ السيرفر: {server}"
USAGE_PROFILE_LABEL = "📋 البروفايل: {profile}"
USAGE_PASSWORD_LABEL = "🔑 الباسورد: <code>{password}</code>"
USAGE_COMMENT_LABEL = "💬 التعليق: {comment}"
USAGE_BYTES_IN = "📥 وارد: {bytes}"
USAGE_BYTES_OUT = "📤 صادر: {bytes}"
USAGE_BYTES_TOTAL = "📊 الإجمالي: {bytes}"
USAGE_UPTIME_LABEL = "⏰ مدة الاتصال: {uptime}"
USAGE_CURRENT_ACTIVE = "<b>🔌 الأجهزة النشطة حالياً:</b>\n{devices}"
USAGE_DEVICE_LINE = "• {address} — {mac} — {uptime}"
USAGE_NO_ACTIVE = "📭 لا توجد أجهزة نشطة حالياً"
USAGE_LIMIT_LABEL = "📊 حد البيانات: {limit}"
USAGE_NO_LIMIT = "غير محدود"


HOTSPOT_STATS = """📊 إحصائيات Hotspot

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

HOTSPOT_STATS_DAY_NOT_FOUND = (
    "⚠️ لا توجد سجلات تصفير لليوم {day}. الأيام المتاحة: {days}."
)

HOTSPOT_STATS_NO_RESET = "ℹ️ لا توجد سجلات تصفير عدادات حسب اليوم."


# ─── HOTSPOT FLOWS STRINGS ──────────────────────────────────────
HOTSPOT_SEARCH_OFFLINE = "\n    🔴 معطل"
HOTSPOT_SEARCH_FOUND = "🔍 تم العثور على {count}"
HOTSPOT_SEARCH_LIMIT = " — يعرض أول {limit}:"

HOTSPOT_KICK_SUCCESS_SINGLE = "✅ تم طرد الجهاز «{host_name}» بنجاح"
HOTSPOT_INVALID_BLOCK_DATA = "❌ بيانات الحظر غير صالحة"
HOTSPOT_INVALID_UNBLOCK_DATA = "❌ بيانات رفع الحظر غير صالحة"

HOTSPOT_EDIT_RESET_SUCCESS = "✅ تم تصفير العدادات\n"
HOTSPOT_EDIT_KICK_COUNT = "🔄 تم طرد المستخدم من {count} جهاز:\n"
HOTSPOT_EDIT_KICK_COUNT_INLINE = "\n🔄 تم طرد المستخدم من {count} جهاز"
HOTSPOT_EDIT_SUCCESS = "✅ تم التعديل بنجاح{kick_msg}\n\n"
HOTSPOT_EDIT_FIELD_PROMPT = "✏️ أرسل القيمة الجديدة للحقل «{field_name}»:\n"
HOTSPOT_EDIT_CURRENT_VALUE = "📌 القيمة الحالية: <code>{current_value}</code>"
HOTSPOT_EDIT_EMPTY_VALUE = "فارغ"

HOTSPOT_PAGINATION_DELETE = "📋 تم العثور على {count} مستخدم ({slice_info}):\n\nاختر المستخدم للحذف:"
HOTSPOT_PAGINATION_EDIT = "📋 تم العثور على {count} مستخدم ({slice_info}):\n\nاختر المستخدم للتعديل:"

HOTSPOT_ADD_BYTES_HINT = "{error}\n\n💡 أو اتركها فارغة للتخطي."
HOTSPOT_ADD_INVALID_UPTIME = "❌ قيمة غير صالحة. الرجاء إدخال رقم صحيح."
HOTSPOT_ADD_USE_BUTTONS = "❌ الرجاء استخدام الأزرار أدناه لاختيار نوع المدة أو التخطي."


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
EXPIRY_ALERT_USER_ROW = (
    "• <b>{name}</b> | بروفايل: {profile} | متبقي: {remaining_days} يوم"
)
EXPIRY_ALERT_EMPTY = (
    "✅ لا توجد اشتراكات منتهية خلال {days} أيام القادمة على {router_name}"
)

# ─── حظر MAC ──────────────────────────────────────────────────
BLOCK_MAC_SUCCESS = "🚫 تم حظر الجهاز <code>{mac}</code> بنجاح.\n\n⚠️ تأكد من وجود Firewall Rule تمنع address-list=hotspot_blocked من الاتصال."
BLOCK_MAC_FAIL = "❌ فشل حظر الجهاز. تحقق من الاتصال بالراوتر."
UNBLOCK_MAC_SUCCESS = "✅ تم رفع الحظر عن <code>{mac}</code>"
UNBLOCK_MAC_FAIL = "❌ فشل رفع الحظر. قد لا يكون الجهاز محظوراً."
BLOCKED_LIST_HEADER = (
    "🚫 <b>الأجهزة المحظورة ({count}):</b>\n\nاضغط على جهاز لرفع حظره:"
)
BLOCKED_LIST_EMPTY = "✅ لا توجد أجهزة محظورة حالياً"

# ─── نظام الفواتير ─────────────────────────────────────────────
SALES_SUMMARY_HEADER = "💰 <b>ملخص المبيعات — آخر {days} يوم</b>\n\n"
SALES_SUMMARY_ROW = "📦 إجمالي الدفعات: {total_batches}\n✅ مدفوعة: {paid_count}\n🆓 غير مدفوعة: {unpaid_count}\n⏳ مرحّلة: {deferred_count}\n💵 الإيرادات: {total_revenue:.2f}"
MARK_PAID_SUCCESS = "✅ تم تحديث حالة الدفع إلى: {status_label}"
MARK_PAID_FAIL = "❌ فشل تحديث حالة الدفع"
PAYMENT_STATUS_LABELS = {
    "paid": "مدفوع ✅",
    "unpaid": "غير مدفوع 🆓",
    "deferred": "مرحّل ⏳",
}

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

# ─── إحصائيات تاريخية (Snapshots) ─────────────────────────────────────
STATS_TREND_HEADER = "\n\n📈 <b>آخر 7 أيام (المستخدمون النشطون):</b>\n<pre>"
STATS_TREND_FOOTER = "</pre>"
STATS_VS_YESTERDAY = "\n\n🔄 <b>مقارنة بالأمس:</b> {comparison}"
STATS_NO_HISTORY = "\n\n📭 لا توجد بيانات تاريخية بعد"

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
BACKUP_BACKGROUND_NOTIFY = "{msg}\n\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء."
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
AUDIT_SUBMENU_COUNT = "{title}\n\n🔢 العدد: {count}"
AUDIT_LIST_EMPTY = "📋 سجل التدقيق\n\n{header}\n\n{no_results}"
AUDIT_PAGE_EMPTY = "📋 سجل التدقيق\n\n{header}\n\n📭 لا توجد سجلات في هذه الصفحة"
AUDIT_LIST_HEADER = "📋 <b>سجل التدقيق</b> ({start}-{end} من {total})"

# ─── WATCHDOG STRINGS ──────────────────────────────────────────
WATCHDOG_QUEUE_UNAVAILABLE = "❌ Job Queue غير متاح"
WATCHDOG_ALREADY_RUNNING = "✅ مراقبة الراوترات تعمل بالفعل"
WATCHDOG_STARTED = "✅ تم بدء مراقبة الراوترات (كل 5 دقائق)"
WATCHDOG_STOPPED = "❌ تم إيقاف مراقبة الراوترات"
WATCHDOG_NO_ROUTERS = "📭 لا توجد روترات محفوظة"
WATCHDOG_STATUS_HEADER = "📊 <b>حالة الراوترات:</b>\n"
WATCHDOG_LAST_OK = "آخر اتصال: {date}"
WATCHDOG_ONLINE = "متصل"
WATCHDOG_LAST_FAIL = "آخر فشل: {date}"
WATCHDOG_NOT_CHECKED = "لم يتم الفحص بعد"
WATCHDOG_VERSION = "   ├─ الإصدار: {version}"
WATCHDOG_ACTIVE_HOTSPOT = "   ├─ مستخدمو Hotspot النشطون: {count}"
WATCHDOG_LAST_BACKUP = "   └─ آخر نسخة احتياطية: {backup}\n"
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
USERMAN_SEARCH_RESULT = "👤 مستخدم User Manager:\n📛 الاسم: {name}\n🔑 الرمز: {pwd}\n📋 البروفايل: {profile}\nوضع الحساب: {status}"
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
USERMAN_UNLINKED_WARNING = "\n\n⚠️ {unlinked} من {total} كارتاً لم يُربط بها البروفايل "

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
TIMEOUT_HEADER = "⏰ <b>إعداد مدة الخمول (Session Timeout)</b>\n\nاختر المدة التي سيتم بعدها إغلاق الجلسة وإجبارك على اختيار الراوتر مجدداً (لحماية النظام):"
TIMEOUT_SAVED = "✅ تم حفظ إعداد الخمول بنجاح.\nالمدة الحالية: "
TIMEOUT_SAVED_NO_LIMIT = "بدون إغلاق (مفتوح دائماً)."
TIMEOUT_SAVED_MINS = "{val} دقيقة."
TIMEOUT_SAVE_ERROR = "❌ حدث خطأ أثناء حفظ الإعداد."
