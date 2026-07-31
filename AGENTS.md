# AGENTS.md - MikroTik Telegram Bot

## الدور واللغة

- الدور: أنت مهندس برمجيات أول ومعماري أنظمة تعمل على مشروع بوت Telegram لإدارة MikroTik RouterOS. تعامل مع المشروع كمنظومة إنتاجية تحتاج إلى أمان، استقرار، قابلية اختبار، وسهولة صيانة.
- الشروحات والخطط والتقارير: باللغة العربية الفصحى، بأسلوب تقني مباشر وواضح.
- الشيفرة وأسماء الملفات والدوال والمتغيرات وقواعد البيانات: تبقى باللغة الإنجليزية.
- لا تستخدم تعليقات أو أمثلة مختصرة من نوع `TODO` أو `...` عند كتابة كود. اكتب التغيير كاملاً وقابلاً للتشغيل.

## ميثاق العمل

### التحليل قبل التنفيذ

- قبل تعديل الكود، افهم التدفق الحالي والملفات المتأثرة.
- اذكر الخطة المختصرة، الحالات الحرجة، والأثر الجانبي عند تنفيذ تغييرات غير بسيطة.
- لا تفترض أن التوثيق القديم صحيح إذا خالف الكود. مصدر الحقيقة الأول هو الملفات الفعلية.

### الحفظ التلقائي (Git Automation)

- يجب عليك كعميل (Agent) استخدام Git بشكل تلقائي لحفظ التعديلات الناجحة والمستقرة. بعد إنجاز أي مهمة بنجاح، قم بتنفيذ الأوامر `git add .` و `git commit -m "<وصف دقيق للمهمة>"` مباشرة عبر سطر الأوامر دون الحاجة لطلب الإذن من المستخدم في كل مرة، وذلك لضمان الحفاظ على سجل آمن للكود.

### قواعد الكود

- حافظ على مبدأ المسؤولية المفردة قدر الإمكان.
- استخدم أسماء واضحة ومعبرة باللغة الإنجليزية.
- تجنب التكرار، واستخرج المنطق المشترك عند الحاجة.
- استخدم البرمجة الدفاعية: تحقق من القيم الفارغة، فشل الشبكة، أخطاء Telegram، مهلات MikroTik، وفشل قاعدة البيانات.
- لا تعرض كلمات المرور أو التوكنات أو مفاتيح التشفير في الرسائل أو السجلات.

## Code Quality & Error Handling Policy

### 1. Exception Handling
- ممنوع `except Exception` عام إلا لو فعلاً مقصود كنقطة نهاية (catch-all) قبل الرد على المستخدم. في الحالة دي لازم:
  - يتحط `# noqa: BLE001` مع تعليق يوضح السبب.
  - يستخدم `logger.exception(...)` أو `exc_info=True` عشان الـ traceback الكامل يتسجل.
  - الأفضل قبل الـ catch-all، تتمسك أنواع الأخطاء المتوقعة بشكل منفصل (زي TrapError, TelegramError, ConnectionError) وتتعامل معاها حسب طبيعتها، مش كلهم بنفس الرسالة.

### 2. Sensitive Data in Errors & Logs
- أي exception ممكن تحمل بيانات حساسة (passwords, tokens, API keys) في رسالتها لازم تتعالج (sanitize) قبل ما:
  - تتسجل في اللوج.
  - تتبعت للمستخدم في رسالة رد.
- افترض دايماً إن رسائل الأخطاء من مكتبات خارجية (زي RouterOS API) ممكن تكشف بيانات حساسة كانت اتبعتت في نفس الطلب.

### 3. Return Values & Variable Naming
- ممنوع متغير واحد يحمل معنيين مختلفين حسب حالة النجاح/الفشل (مثال: `version` بيبقى رقم إصدار عند النجاح، ورسالة خطأ عند الفشل). استخدم:
  - dataclass أو NamedTuple بحقول واضحة (success, value, error_message).
  - أو متغيرين منفصلين واضحين بالاسم.

### 4. External Calls Outside try/except
- أي استدعاء لـ API خارجي أو دالة ممكن تفشل (network call، إرسال رسالة Telegram، قراءة قاعدة بيانات) لازم يكون جوه try/except، حتى لو مكانه في نص الفنكشن مش في المكان "المتوقع" فيه فشل.
- لو الفشل هنا معناه إن كود لاحق (زي cleanup) مش هيتنفذ، استخدم try/finally عشان تضمن التنظيف بيحصل في كل الأحوال.

### 5. Input Validation
- أي بيانات جاية من المستخدم مباشرة (زي `update.message.text`) لازم تتفحص قبل الاستخدام — تأكد إنها مش None ومطابقة للنوع المتوقع، قبل ما تتبعت لأي دالة تانية.

### 6. Context/State Defaults
- ممنوع استخدام قيمة افتراضية صامتة (زي `.get(key, "")`) لبيانات أساسية لازمة لصحة العملية (زي IP أو ID). لو القيمة مش موجودة، ده لازم يتعامل معاه كخطأ صريح (رسالة واضحة للمستخدم + توقف العملية) بدل ما يكمّل بقيمة فاضية أو وهمية.

### 7. Imports Inside Functions
- لو import محطوط جوه فنكشن (غالباً لتجنب circular import)، لازم يتحط تعليق فوقه يوضح السبب، عشان محدش ينقله لفوق الملف بالغلط.

### 8. Self-Review Checklist
قبل ما تعتبر أي كود بيتعامل مع I/O خارجي (Telegram, DB, router API) جاهز، راجع:
- [ ] كل except له سبب واضح ومش عام من غير مبرر
- [ ] مفيش بيانات حساسة ممكن تتسرب في log أو رسالة رد
- [ ] كل متغير بيحمل معنى واحد ثابت مهما كانت الحالة
- [ ] كل استدعاء خارجي محاط بـ try، والتنظيف مضمون بـ finally لو لازم
- [ ] المدخلات من المستخدم اتفحصت قبل الاستخدام
- [ ] مفيش قيم افتراضية صامتة لبيانات حرجة

### الاختبار والتتبع

- أي تغيير في handlers يجب أن يمر عبر `scripts/validate_handlers.py`.
- أي تغيير في تسجيل الأوامر يجب أن ينعكس في `bot/registrations.py`, `utils/bot_commands.py`, و`bot/messages.py` عند الحاجة.
- أي رمز `callback_data` (ثابت أو ديناميكي) يجب أن يُعرّف في `bot/handlers/callback_constants.py` (`CALLBACKS`/البناة)، وأنماط التسجيل في `PATTERNS`، ويُستدعى من `bot/registrations.py` باسم النمط لا بنمط مضمّن.
- استخدم `run_blocking()` للعمليات المتزامنة أو البطيئة حتى لا يتم حجب event loop.
- استخدم `send_error()` أو معالجة خطأ واضحة عند فشل عمليات MikroTik أو Telegram.
- حافظ على `request_id` logging الموجود عبر `utils/request_id.py` و`utils/logging_setup.py`.

## Quick Start

```bash
cd mikrotik_bot
pip install -r requirements.txt
cp .env.example .env
python main.py
```

> إذا كان `python` يشير إلى مسار معطوب (مثل `venv` يشير إلى Python غير موجود، أو تداخل `WindowsApps`/`uv`)، استخدم `py -3.12` صراحةً:
> `py -3.12 -m pip install -r requirements.txt` ثم `py -3.12 main.py`.

يجب تعبئة القيم التالية في `.env` قبل التشغيل:

| المتغير | مطلوب | الوصف |
|---------|-------|-------|
| `BOT_TOKEN` | نعم | توكن Telegram Bot. |
| `ADMIN_IDS` | نعم | معرفات مشرفي Telegram مفصولة بفواصل. |
| `ENCRYPTION_KEY` | نعم | مفتاح Fernet صالح. `config.py` يوقف التشغيل إذا كان مفقوداً أو قصيراً. |
| `BOT_HOST` | يُنصح به | عنوان IP للخادم الذي يستخدمه الراوتر للاتصال بالخادم (مطلوب للنسخ الاحتياطي والاستعادة). |
| `FILE_SERVER_SECRET` | اختياري | توكن Bearer لخادم نقل الملفات. يُولّد تلقائياً إذا لم يُعَرَّف. |
| `FILE_SERVER_PORT` | اختياري | منفذ خادم نقل الملفات (الافتراضي: 8729). |
| `SCHEDULE_FULL_BACKUP` | اختياري | عند `true`، النسخ الاحتياطي اليومي يشمل نسخة كاملة. الافتراضي: `false`. **تنبيه:** يُرسل كلمة مرور الراوتر نصاً عبر FTP. شغّل فقط في شبكة إدارة معزولة. |

## بنية المشروع الحالية

```text
mikrotik_bot/
├── main.py                    # نقطة التشغيل: init_db, Application, JobQueue, post_init, polling, graceful shutdown
├── config.py                  # تحميل .env والتحقق من BOT_TOKEN, ADMIN_IDS, ENCRYPTION_KEY
├── utils/
│   ├── handler_registry.py    # بناء ConversationHandler الرئيسي والمعالجات المستقلة
│   ├── bot_commands.py        # قائمة أوامر Telegram السريعة
│   ├── admin_decorator.py     # @admin_only و @require_router مع rate limit
│   ├── async_blocking.py      # run_blocking للعمليات المتزامنة
│   ├── callback_utils.py      # safe_answer_callback و is_duplicate_callback
│   ├── chat_cleaner.py        # تتبع الرسائل والتنظيف التلقائي
│   ├── crypto.py              # تشفير وفك تشفير كلمات مرور الراوترات
│   ├── error_response.py      # تصنيف الأخطاء وتعقيم الرسائل
│   ├── formatters.py          # parse_bytes, format_bytes, sanitize_api_response
│   ├── logging_setup.py       # request_id logging
│   ├── log_helpers.py         # log_api_call لتسجيل وتوقيت استدعاءات API الخارجية
│   ├── pagination.py          # أدوات الترقيم (pagination) للقوائم
│   ├── request_id.py          # تتبع request_id عبر ContextVar
│   ├── singleton_lock.py      # منع تشغيل أكثر من نسخة بوت
│   ├── tg_helpers.py          # دوال مساعدة لـ Telegram
│   └── validators.py          # التحقق من المدخلات
├── bot/
│   ├── __init__.py            # حزمة bot
│   ├── registrations.py       # التسجيل المركزي للأوامر، callbacks، states، fallbacks
│   ├── registration_parts/    # أقسام التسجيل المنفصلة
│   │   ├── conversation.py    # تسجيل ConversationHandler
│   │   ├── separate_handlers.py # تسجيل المعالجات المستقلة
│   │   └── standalone.py      # تسجيل الأوامر المستقلة
│   ├── handlers/
│   │   ├── __init__.py        # تصدير المعالجات
│   │   ├── batch.py           # /batches دفعات الكروت
│   │   ├── commands_basic.py  # /cancel, /clean, /metrics, /sync, معالج الخطأ
│   │   ├── common/            # /start, /help, /clean, /metrics, /sync والقوائم
│   │   ├── common.py          # واجهة توافق لإعادة التصدير
│   │   ├── handler_utils.py   # دوال مساعدة مشتركة
│   │   ├── menus.py           # go_back للتنقل بين القوائم
│   │   ├── roles.py           # /roles إدارة أدوار المشرفين
│   │   ├── routers.py         # واجهة توافق لتدفقات إدارة الروترات
│   │   ├── router_system.py   # عمليات النظام على الروترات
│   │   ├── session_models.py  # نماذج dataclass لحالة المحادثة
│   │   ├── timeout.py         # /timeout إدارة مهلة الجلسة
│   │   ├── hotspot_add.py     # إضافة مستخدم Hotspot
│   │   ├── hotspot_edit.py    # تعديل مستخدم Hotspot
│   │   ├── hotspot_delete.py  # حذف مستخدم Hotspot
│   │   ├── hotspot_search.py  # بحث وطرد hosts
│   │   ├── hotspot_cards.py   # إنشاء كروت Hotspot PDF
│   │   ├── hotspot_common.py  # دوال pagination المشتركة لـ Hotspot
│   │   ├── hotspot_flow_utils.py # أدوات مساعدة مشتركة محدودة لتدفقات Hotspot
│   │   ├── hotspot_report.py  # تقرير Hotspot وتصدير CSV
│   │   ├── hotspot.py         # إحصائيات Hotspot التفصيلية
│   │   ├── userman.py         # User Manager cards/list/profiles
│   │   ├── userman_search.py  # بحث User Manager
│   │   ├── backup.py          # النسخ اليدوي والجدولة والتحميل
│   │   ├── backup_restore.py  # استعادة system وUser Manager backups
│   │   ├── stats.py           # إحصائيات Hotspot/User Manager العامة
│   │   ├── settings.py        # إعدادات PDF
│   │   ├── audit.py           # سجل التدقيق /logs
│   │   ├── usage.py           # تقرير استخدام مستخدم Hotspot
│   │   ├── watchdog.py        # مراقبة حالة الروترات
│   │   ├── states.py          # WaitingState enum
│   │   ├── callback_constants.py # ثوابت/بناة callback_data وأنماط PATTERNS (المصدر الوحيد للـ tokens)
│   │   └── constants.py       # WAITING_* constants
│   │   └── router_flows/
│   │       ├── __init__.py    # إعادة تصدير تدفقات الروترات
│   │       ├── discovery.py   # اكتشاف الروترات
│   │       ├── manual_add.py  # إضافة روتر يدوياً مع التحقق
│   │       ├── reboot.py      # إعادة تشغيل الراوتر
│   │       ├── rename.py      # إعادة تسمية الراوتر
│   │       └── saved.py       # الروترات المحفوظة
│   ├── helpers/profiles.py    # جلب وتخزين أسماء البروفايلات مؤقتاً
│   ├── keyboards.py           # كل InlineKeyboard builders
│   ├── messages.py            # النصوص العربية للمستخدم
│   ├── profile_callbacks.py   # callback index cache للبروفايلات
│   └── router_selector.py     # الراوتر المختار وحالة التنقل لكل مستخدم
├── core/
│   ├── __init__.py            # حزمة core
│   ├── mikrotik_api.py        # واجهة تنفيذ لأوامر RouterOS مع retry/throttle
│   ├── mikrotik_client.py     # MikroTik client wrapper
│   ├── connection_pool.py     # connection pool وtimeouts وmetrics
│   ├── cache.py               # TTLCache عام (dict-based مع threading.Lock)
│   ├── exceptions.py          # فئات الاستثناءات المخصصة
│   ├── metrics.py             # مقاييس Prometheus: record_action, record_error, record_component_result, record_db_query, record_mikrotik_request, record_telegram_request, get_health_status, get_error_rate
│   ├── hotspot_manager.py     # Hotspot CRUD/search/kick/cards
│   ├── hotspot_blocking.py    # حظر/فك حظر MAC عبر address-list
│   ├── hotspot_expiry.py      # كشف المستخدمين المنتهيين
│   ├── hotspot_search.py      # بحث المضيفين وإثراء DHCP leases وطرد
│   ├── hotspot_stats.py       # إحصائيات Hotspot مع تصفية يوم إعادة الضبط
│   ├── userman_manager.py     # User Manager cards/list
│   ├── backup_service.py      # واجهة توافق لخدمات backup/restore
│   ├── backup/
│   │   ├── __init__.py        # حزمة backup
│   │   ├── files.py           # أدوات آمنة للمسارات والتنظيف والتحقق
│   │   ├── file_server.py     # خادم ملفات لتخزين النسخ الاحتياطية
│   │   ├── ftp.py             # رفع/تحميل عبر FTP
│   │   ├── system.py          # منطق system backup
│   │   ├── userman.py         # منطق User Manager backup/restore
│   │   └── restore.py         # استعادة system backups المحلية
│   ├── backup_scheduler.py    # جدولة النسخ اليومي + فحص انتهاء الاشتراكات + لقطات إحصائية يومية
│   ├── network_probe.py       # MNDP/ARP/port scan primitives
│   ├── network_scanner.py     # discovery orchestrator
│   ├── profile_cache.py       # TTL cache للبروفايلات
│   ├── profile_sync.py        # جلب User Manager profiles
│   ├── messages_expiry.py     # إدارة انتهاء صلاحية الرسائل
│   ├── card_models.py         # نماذج بيانات الكروت
│   ├── chart_generator.py     # إنشاء الرسوم البيانية للتقارير
│   ├── reports_excel.py       # إنشاء تقارير Excel
│   ├── reports_export.py      # وظائف التصدير
│   ├── router_info.py         # مساعدات معلومات الروتر
│   ├── stats.py               # إحصائيات عامة
│   ├── router_key.py          # helper لمفاتيح discovered routers
│   └── watchdog.py            # health status in-memory
├── database/
│   ├── __init__.py            # حزمة database
│   ├── models.py              # SQLite schema, CRUD, migrations خفيفة
│   ├── execute.py             # timed_execute — توقيت وتتبع استعلامات DB مع record_db_query
│   └── repositories/          # مستودعات البيانات (CRUD)
│       ├── admin_roles.py     # إدارة أدوار المشرفين
│       ├── audit_logs.py      # سجلات التدقيق والتنظيف
│       ├── backups.py         # مهام وإعدادات النسخ الاحتياطي
│       ├── card_batches.py    # دفعات الكروت وملخص المبيعات
│       ├── chat_messages.py   # الرسائل المتعقبة
│       ├── operator_permissions.py # أذونات المشغّل
│       ├── pdf_settings.py    # إعدادات PDF (قائمة بيضاء للأعمدة)
│       ├── routers.py         # الروترات المكتشفة CRUD
│       ├── router_health.py   # سجل صحة الروترات
│       ├── stats_snapshots.py # لقطات الإحصائيات
│       └── user_sessions.py   # جلسات المستخدمين وتتبع النشاط
├── pdf/                       # PDF generation باستخدام reportlab وqrcode ودعم العربية
│   ├── __init__.py            # حزمة pdf
│   ├── card_generator.py      # منطق إنشاء الكروت
│   ├── card_renderer.py       # عرض الكروت
│   ├── pdf_renderer.py        # عرض PDF
│   └── pdf_settings.py        # إعدادات PDF
├── scripts/                   # validate_handlers, validate_routeros_paths, check_type_ignore, snapshot_release, e2e_smoke, stress_test
└── tests/                     # pytest tests للوحدات والتكامل
```

## المعمارية الحالية

- يستخدم المشروع `python-telegram-bot` مع `ConversationHandler` رئيسي لمعظم التدفقات متعددة الخطوات، إضافة إلى `ConversationHandler`ات مستقلة لبعض التدفقات القصيرة مثل rename.
- `main.py` لا يسجل المعالجات يدوياً؛ التسجيل المركزي موجود في `bot/registrations.py` ويتم بناؤه عبر `utils/handler_registry.py`.
- `bot/handlers/routers.py` لم يعد يحمل التنفيذ الكامل لتدفقات الروترات؛ هو واجهة توافق تعيد تصدير التنفيذ الموجود في `bot/handlers/router_flows/`.
- `core/backup_service.py` لم يعد يحمل كل منطق النسخ الاحتياطي داخلياً؛ هو واجهة توافق فوق `core/backup/`.
- `concurrent_updates(False)` مطلوب لاستقرار `ConversationHandler`.
- `post_init()` يضبط أوامر Telegram، يستعيد جدول النسخ الاحتياطي، ويبدأ watchdog إذا لم يكن موجوداً.
- حالة الراوتر المختار تحفظ في SQLite داخل `user_sessions`، بينما `nav_back` وبعض بيانات المحادثة تحفظ مؤقتاً في `context.user_data`.
- طبقة `core/` يجب أن تبقى قدر الإمكان بدون اعتماد مباشر على Telegram.

### إدارة السجلات (Logging)

- إعداد السجلات يتم في بداية `main.py` عبر استدعاء `configure_logging(logging.INFO)` من `utils/logging_setup.py`، بدون استخدام `logging.basicConfig` لتجنب إنشاء `StreamHandler` ثانٍ بمستوى `NOTSET`. الـ console handler يُظهر `INFO` فما فوق فقط، بينما الـ file handler (`logs/mikrotik-bot.log`) يسجل `DEBUG` فما فوق بتنسيق JSON.
- المكتبات المزعجة (`httpx`, `httpcore`, `apscheduler`, `PIL`, `librouteros`, `utils.chat_cleaner`) تُكبَت إلى `WARNING` عبر `setLevel()` قبل استدعاء `configure_logging()`.
- لتتبع الطلبات، يُستخدم `request_id` عبر `ContextVar` في `utils/logging_setup.py`، ويتم حقنه تلقائياً في كل سجل عبر `RequestIdFilter` المضاف إلى الـ root logger وكل handlers.
- **Component tagging**: يتم تتبع المكون النشط عبر `component` ContextVar باستخدام `bind_component()` من `utils/logging_setup.py`. يتم تعيينه في نقاط الدخول الرئيسية: `COMPONENT_SYSTEM` في `main.py` (post_init, run_with_shutdown)، و`COMPONENT_HANDLER` في `utils/handler_registry.py` (_build_wrapper و error handler)، و`COMPONENT_CALLBACK` في `utils/callback_utils.py`.
- **Sanitization**: يجب عدم تسجيل أي بيانات حساسة (كلمات مرور، توكنات، مفاتيح API) في السجلات. يتم استخدام `sanitize_log_data()` من `utils/formatters.py` لتنقية بيانات الاستجابة قبل تسجيلها في السجلات، خاصة عند مستوى `ERROR` أو `WARNING`.
- **Duration tracking**: جميع العمليات التي تتجاوز `_DEFAULT_DURATION_WARN_MS` (5 ثوانٍ) تُسجّل بتنبيه. يتم تتبع مدة تنفيذ العمليات باستخدام `duration_ms` في كل سجل منظم.
- **Sensitive data in errors**: أي خطأ من مكتبات خارجية (مثل RouterOS API) قد يكشف بيانات حساسة يجب تنقيتها عبر `sanitize_log_data()` قبل تسجيلها أو إرسالها للمستخدم.

### المراقبة والمقاييس (Observability & Metrics)

- **نظام المراقبة**: يستخدم `core/metrics.py` لتوفير endpoint مقاييس Prometheus عبر `/metrics` (في `commands_basic.py`). المسار معرّف في `config.METRICS_ENDPOINT_PATH`.
- **Prometheus metrics** المصدرة:
  - `bot_actions_total` — عدد العمليات (system, mikrotik, callback, command) مع labels: `user_id`, `command`, `success`, `error_category`.
  - `bot_action_duration_seconds` — histogram لزمن العمليات.
  - `bot_db_queries_total` — عدد استعلامات DB مع `operation` و `table` labels.
  - `bot_db_query_duration_seconds` — histogram لزمن استعلامات DB.
  - `bot_mikrotik_requests_total` — عدد طلبات RouterOS API مع `router` و `command` labels.
  - `bot_mikrotik_request_duration_seconds` — histogram لزمن طلبات API.
  - `bot_telegram_requests_total` — عدد طلبات Telegram مع `handler` label.
  - `bot_telegram_handler_duration_seconds` — histogram لزمن معالجات Telegram.
  - `bot_error_rate` — gauge لمعدل الخطأ لكل مكون (نافذة منزلقة 10 دقائق).
  - `bot_health_status` — gauge: 0=سليم, 1=منحط, 2=حرج (عتبات: 10% WARN, 25% CRIT).
  - `bot_duration_warnings_total` — تحذيرات العمليات البطيئة (>5 ثوانٍ).
- **Component Health**: `get_health_status()` تفحص نسبة فشل كل مكون وتصنف الحالة.
- **Error Rate**: `get_error_rate(component)` تحسب معدل الخطأ في نافذة منزلقة زمنية.
- **توقيت DB**: `database/execute.py` يوفر `timed_execute()` لتغليف استعلامات SQLite مع تتبع وتسجيل تلقائي للمدة وعدد الصفوف.
- **توقيت API خارجي**: `utils/log_helpers.py` يوفر `log_api_call()` (decorator/context manager) لتسجيل وتوقيت استدعاءات MikroTik API و Telegram API.
- **ContextVars للتتبع**: `user_id`, `chat_id`, `router_key`, `command`, `success`, `duration_ms`, `error_category` تُحقن عبر `utils/logging_setup.py` ويتم تسجيلها تلقائياً في كل سجل.
- **Component tagging**: يتم تتبع المكون النشط (`system`, `handler`, `callback`, `background`) عبر ContextVar `component` وتسجيله في كل سجل وكل metric.

## الأوامر الحالية

الأوامر المعروضة في قائمة Telegram السريعة معرفة في `utils/bot_commands.py`:

- `/start` - القائمة الرئيسية.
- `/help` - المساعدة.
- `/add` - إضافة مستخدم Hotspot.
- `/edit` - تعديل مستخدم Hotspot.
- `/delete` - حذف مستخدم Hotspot.
- `/search` - بحث عن مستخدم أو جهاز.
- `/cards` - إنشاء كروت Hotspot.
- `/userman` - إدارة User Manager.
- `/backup` - قائمة النسخ الاحتياطي.
- `/routers` - إدارة الروترات المحفوظة.
- `/addrouter` - إضافة روتر يدوياً (IP/منفذ/مستخدم/كلمة مرور/اسم).
- `/settings` - إعدادات PDF.
- `/reboot` - إعادة تشغيل الراوتر المختار.
- `/timeout` - إعداد مدة الخمول وحماية الجلسة.
- `/metrics` - مقاييس Prometheus، أداء الاتصالات، وسلامة المكونات الداخلية.
- `/logs` - سجل التدقيق.
- `/sync` - إعادة ضبط قائمة الأوامر السريعة.
- `/clean` - تنظيف الشات.
- `/usage` - تقرير استخدام مستخدم.
- `/watchdog` - حالة مراقبة الروترات.
- `/watchdog_start` - بدء مراقبة الروترات.
- `/cancel` - إلغاء المحادثة الحالية.
- `/reports` - التقارير.
- `/report` - تقرير المبيعات.
- `/roles` - إدارة أدوار المشرفين.
- `/batches` - دفعات الكروت.
- `/sales` - المبيعات.
- `/add_customer` - إضافة عميل.
- `/remove_customer` - إزالة عميل.

## النتائج المتوقعة (Expected Results)

يصف هذا القسم السلوك المتوقع لكل flow من منظور المستخدم النهائي. يُستخدم كمرجع لكتابة الاختبارات وتوثيق السلوك. لا يكرر تفاصيل الت implementation vorhand في Docstrings.

### إدارة Hotspot

| Flow | النتيجة المتوقعة |
|------|------------------|
| `/add` (إضافة مستخدم) | يتحقق من عدم تكرار الاسم → يجلب البروفايلات من الراوتر → يُنشئ المستخدم بالبيانات المدخلة → يعرض رسالة تأكيد بالاسم والبروفايل. يُعيد `WAITING_USERNAME` لتمكين الإضافة المتتالية. |
| `/edit` (تعديل مستخدم) | يبحث عن المستخدم → يعرض قائمة الحقول القابلة للتعديل (الاسم/كلمة المرور/البروفايل/البايتات/الوقت/التعليق) → يُنفّذ التعديل على الراوتر → يعرض تأكيداً. يدعم kick وreset-counters وtoggle disable/enable. |
| `/delete` (حذف مستخدم) | يبحث عن المستخدم → يعرض تأكيداً بالبيانات → عند التأكيد يحذف من الراوتر ويعمل `active-remove` للطرد. يُعيد `ConversationHandler.END`. |
| `/search` (بحث hosts) | يدعم بحث `user:`, `mac:`, `ip:`, `comment:` → يعرض نتائج مُرتبة بترقيم → يسمح بعرض التفاصيل + طرد + حظر MAC + فك حظر + عرض المحظورين. |
| `/cards` (إنشاء كروت) | يحدد العدد (حد أقصى 500) / الطول / البادئة / النوع (مختلفة/متشابهة/بدون كلمة مرور) / البروفايل / مدة الصلاحية / حد البايتات → يولّد PDF ويُرسله كمرفق → يحفظ الدفعة في DB مع ملخص المبيعات. |
| `report` (تقرير Hotspot) | يعرض إحصائيات شاملة (إجمالي/نشط/غير نشط/حسب البروفايل) + تصدير CSV + تصدير Excel. |
| `/usage` (تقرير استخدام) | يبحث عن المستخدم → يعرض: الحالة/الخادم/البروفايل/كلمة المرور (مموّهة)/الحد/الوقت/التعليق/بايتات inbound+outbound+إجمالي + الأجهزة النشطة حالياً. |

### إدارة User Manager

| Flow | النتيجة المتوقعة |
|------|------------------|
| `/userman` → cards (كروت UM) | نوع البطاقة / البروفايل / حالة الدفع / ربط MAC / البادئة / العدد → يولّد PDF ويُرسله → يحفظ الدفعة. |
| `/userman` → list (قائمة UM) | يعرض جميع مستخدمي User Manager مع الحالة والبروفايل. |
| `/userman` → profiles (بروفايلات UM) | يعرض جميع البروفايلات مع الأسعار والمدد. |
| `userman_search` (بحث UM) | يبحث → يعرض نتائج مُرتبة → يسمح بعرض التفاصيل + تعديل + طرد + حذف + تعيين بروفايل. |

### إدارة الروترات

| Flow | النتيجة المتوقعة |
|------|------------------|
| `discover` (اكتشاف) | يمسح الشبكة عبر MNDP/ARP → يعرض الروترات المكتشفة → يطلب بيانات الاعتماد (مستخدم/كلمة مرور) → يختبر الاتصال → يحفظ في DB ويعيّنه كراوتر مختار. |
| `manual_add` (إضافة يدوية) | IP → منفذ (افتراضي 8728) → مستخدم → كلمة مرور → اسم → ملخص تأكيد → اختبار اتصال → حفظ. يتحقق من عدم تكرار IP. |
| `rename` (إعادة تسمية) | يعرض الاسم الحالي → يطلب اسماً جديداً → يحدّث alias في DB + يُبطئ كاش الإصدار. |
| `reboot` (إعادة تشغيل) | يعرض تأكيداً → يُنفذ `system/reboot` عبر API. يدعم إعادة التشغيل من القائمة المحفوظة أيضاً. |
| `saved` (الروترات المحفوظة) | يعرض القائمة مع حالة الاتصال (متصل/معطّل) → يسمح بالاتصال + الحذف + تحديث الحالة + عرض التفاصيل. |

### النسخ الاحتياطي والاستعادة

| Flow | النتيجة المتوقعة |
|------|------------------|
| `backup` (نسخة كاملة) | يبدأ نسخة احتياطية كعملية خلفية عبر JobQueue → يرفع الملف عبر FTP → يحفظ السجل في DB. |
| `backup userman` (نسخة UM) | يصدّر User Manager إلى tar → يرفع عبر FTP → يحفظ السجل. |
| `restore` (استعادة) | يعرض النسخ المتاحة من الراوتر → يطلب تأكيداً → يُجري الاستعادة عبر API + reload. |
| `restore userman` | يعرض ملفات UM المحفوظة → يطلب تأكيداً → يستعيد عبر API. |
| `schedule` (جدولة) | تفعيل/تعطيل النسخ اليومي + ضبط الوقت (HH:MM). |
| `download` (تحميل) | يُرسل ملف النسخة الاحتياطية كمرفق في المحادثة. |

### النظام والإعدادات

| Flow | النتيجة المتوقعة |
|------|------------------|
| `/timeout` | يعرض خيارات: 5/15/30/60 دقيقة أو بدون حد → يحفظ في `user_sessions.timeout_minutes`. |
| `/roles` (الأدوار) | يعرض أدوار جميع المشرفين → يسمح بتعيين super_admin/admin/operator/viewer/customer → يدير المشغّلين وربطهم بالروترات. |
| `/logs` (سجل التدقيق) | يعرض السجلات مع فلاتر (راوتر/مشرف/عملية/مدة) + ترقيم صفحات + تفاصيل كل سجل. |
| `/metrics` | يعرض مقاييس الاتصال (نجاح/فشل/متوسط الوقت) + حالة صحة المكونات (سليم/منحط/حرج) + حالة استهلاك السيرفر (CPU/RAM). |
| `/settings` (إعدادات PDF) | يعرض مجموعات الإعدادات (نص/تخطيط/QR) → يسمح بتعديل كل إعداد مع تحقق من القيم. |
| `/watchdog` | مراقبة دورية للروترات: بدء/إيقاف/عرض الحالة/تحديث فوري. |

### القوائم والتنقل

| Flow | النتيجة المتوقعة |
|------|------------------|
| `/start` | يعرض القائمة الرئيسية مع اسم المشرف + معلومات الراوتر المختار + نوع النظام. |
| `go_back` | يعود للقائمة السابقة بناءً على `nav_back` المخزنة. |
| `end_conversation` | ينظف حالة المحادثة → يعرض القائمة المحددة (main/hotspot/userman/etc). |

### التقارير والدفعات

| Flow | النتيجة المتوقعة |
|------|------------------|
| `/batches` (الدفعات) | يعرض دفعات الكروت مع ملخص المبيعات → تفاصيل الدفعة + تحديث حالة الدفع (مدفوع/غير مدفوع/مؤجل) + إعادة إنشاء PDF + مشاركة الكروت. |
| `/reports` | يعرض قائمة التقارير المتاحة. |

## إضافة أمر جديد

عند إضافة أمر جديد `/xyz`، حدّث هذه المواضع:

1. إنشاء handler في ملف مناسب داخل `bot/handlers/` مع `@admin_only` عند الحاجة.
2. تصدير handler من `bot/handlers/__init__.py` إذا كان نمط المشروع الحالي يحتاجه.
3. استيراد وتسجيل handler في `bot/registrations.py` باستخدام `standalone`, `entry_point`, `state`, أو `fallback` حسب نوع الأمر. إن احتاج الأمر `callback_data` جديداً، عرّفه في `bot/handlers/callback_constants.py` (`CALLBACKS` أو أحد البناة) وأضف نمطه إلى `PATTERNS`، ثم استخدم `PATTERNS["<name>"]` في التسجيل.
4. إضافة الأمر إلى `utils/bot_commands.py` حتى يظهر في قائمة `/` داخل Telegram.
5. تحديث `HELP` في `bot/messages.py` إذا كان الأمر موجهاً للمستخدم.
6. تشغيل `python scripts/validate_handlers.py` بعد التعديل.

ملاحظة: لا تضف تسجيل المعالجات مباشرة إلى `main.py` إلا إذا كان هناك سبب معماري واضح. المسار الحالي هو `bot/registrations.py`.

## قواعد مهمة في MikroTik API

- مفتاح الراوتر المحفوظ يأخذ الشكل `discovered_{db_id}`.
- المنفذ الافتراضي لخدمة API هو `8728` من `config.DEFAULT_API_PORT`.
- `ip/hotspot/host/print` لا يحتوي دائماً على `host-name`؛ يتم إثراؤه من DHCP leases بالـ MAC.
- `ip/hotspot/active/print` يستخدم في عمليات طرد المستخدمين النشطين.
- `reset-counters` يستخدم `numbers=` وليس `.id`.
- مسار User Manager يختلف بين RouterOS v6 وv7، ويحدد عبر `mikrotik_api.get_userman_base_path()`.
- كاش الإصدار (`router_versions`) له صلاحية 24 ساعة؛ بعد ترقية RouterOS أو إعادة تسمية الراوتر نادِ `mikrotik_api.invalidate_version(router_key)` لإبطال الكاش وإعادة اختيار المسار الصحيح. المرجع الكامل في `docs/routeros-v6-v7-compatibility.md`.
- استخدم `execute_long()` للعمليات الثقيلة مثل backup أو جلب قوائم كبيرة.

## إعدادات الاتصال ومهلة النسخ الاحتياطي

### Connection Pool (`core/connection_pool.py`)

| الإعداد | القيمة | الوصف |
|---------|--------|-------|
| `MAX_CONNECTIONS_PER_ROUTER` | 3 | عدد الاتصالات المتزامنة لكل راوتر |
| `CONNECT_TIMEOUT` | 10 ثوانٍ | مهلة إنشاء الاتصال |
| `API_TIMEOUT` | 30 ثانية | مهلة عامة لأوامر API |
| `LONG_TIMEOUT` | 120 ثانية | مهلة للعمليات الثقيلة (backup، قوائم كبيرة) |
| `MAX_RETRIES` | 2 | عدد محاولات إعادة الاتصال |
| `RETRY_DELAY` | 1 ثانية | تأخير بين المحاولات |

### Rate Limits (`utils/admin_decorator.py`)

| العملية | الحد الزمني |
|---------|-----------|
| reboot | 10 ثوانٍ |
| backup | 30 ثانية |
| restore | 60 ثانية |
| delete | 5 ثوانٍ |
| add | ثانيتان |
| edit | ثانيتان |
| أخرى | ثانية واحدة |

### Backup Schedule

| الإعداد | القيمة | الوصف |
|---------|--------|-------|
| القيمة الافتراضية | 03:00 | ساعة التشغيل عبر `start_daily(hour=3, minute=0)` في `core/backup_scheduler.py` |
| `BACKUP_JOBS_RETENTION_PER_ROUTER` | 50 | سجلات النسخ المحتفظ بها لكل راوتر |
| `MAX_LOCAL_BACKUPS` | 10 | نسخ محلية قصوى |
| `MAX_ROUTER_BACKUPS` | 5 | نسخ احتياطية قصوى على الراوتر |

### File Server (`core/backup/file_server.py`)

| الإعداد | القيمة | الوصف |
|---------|--------|-------|
| `FILE_SERVER_PORT` | 8729 | منفذ HTTP لنقل الملفات |
| `FILE_SERVER_SECRET` | (يُولّد تلقائياً) | توكن Bearer للمصادقة |
| `_MAX_UPLOAD_BYTES` | 100 MB | حجم الرفع الأقصى |
| `_ALLOWED_EXTENSIONS` | .backup, .rsc, .umb, .tar | الامتدادات المسموحة |

## قواعد الأمان

- `BOT_TOKEN`, `ADMIN_IDS`, و`ENCRYPTION_KEY` مطلوبة في `config.py`.
- اتصال MikroTik API على المنفذ `8728` غير مشفّر؛ شغّل البوت داخل شبكة إدارة معزولة وقيّد خدمة `api` على IP جهاز البوت. التفاصيل في `docs/routeros-api-security.md`. لا تُفرض API-SSL أو REST كمسار أساسي لأن الراوترات قد لا تملك شهادة SSL ولا يغطي REST إصدار v6 جيداً.
- لا تحفظ أو تعرض كلمات المرور في logs أو رسائل Telegram.
- `update_pdf_settings()` يستخدم whitelist للأعمدة؛ لا تبن SQL ديناميكياً خارج هذا النمط.
- `decrypt_password()` (معرّفة في `utils/crypto.py` وتُعاد تصديرها عبر `database/models.py`) يعيد نصاً فارغاً عند فشل الفك ولا تعيد ciphertext.
- استخدم `is_duplicate_callback()` في callbacks التي قد تؤدي إلى عمليات خطرة أو مزدوجة مثل reboot وbackup.
- لا ترفع `.env`, `mikrotik_bot.db`, `logs/`, `venv/`, أو محتويات `backups/` إلى Git (مستثناة في `.gitignore`).
- المجموعات (group chats) تُتجاهل صامتاً في `admin_decorator.py:111,163`. البوت يعمل فقط في المحادثات الفردية.


## قواعد البيانات

- قاعدة البيانات: SQLite عبر `database/models.py` مع Alembic للترحيل.
- لا تقم بإنشاء جداول مباشرة في الكود؛ استخدم `alembic/` لإنشاء الترحيلات.
- الـ CRUD يُنفَّذ في `database/repositories/` بدوال مخصصة لكل جدول.

| الجدول | الوصف |
|--------|-------|
| `discovered_routers` | الروترات المكتشفة يدوياً أو تلقائياً (IP، MAC، اسم مستخدم، كلمة مرور مشفرة، حالة النشاط، والمالك) |
| `user_sessions` | جلسات مستخدمي التيليجرام والراوتر المختار لكل منهم ومهلة الخمول |
| `logs` | سجل التدقيق (Audit Log) لتوثيق جميع العمليات على الروترات |
| `admin_roles` | إدارة أدور المشرفين (super_admin / admin / operator / viewer / customer) وصلاحياتهم |
| `card_batches` | دفعات كروت Hotspot المُنشأة مع بيانات المبيعات والملف بصيغة JSON |
| `pdf_settings` | الإعدادات الوحيدة (Singleton) لتخصيص شكل PDF الكروت |
| `backup_settings` | الإعدادات الوحيدة (Singleton) لجدولة النسخ الاحتياطي التلقائي |
| `backup_jobs` | تسجيل مهام النسخ الاحتياطي المنجزة لكل راوتر مع حالتها |
| `router_health_log` | سجل صحة الروترات (متصل/معطّل) مع الوقت ورسائل الخطأ |
| `stats_snapshots` | لقطات الإحصائيات اليومية لكل راوتر |
| `tracked_messages` | تتبع رسائل البوت لتنظيفها تلقائياً عند انتهاء صلاحيتها |
| `operator_router_permissions` | ربط المشغّلين بالروترات المسموح لهم بالوصول إليها |

## Quality Gates

يجب استيفاء معايير الجودة الصارمة التالية باستمرار كجزء من الدستور البرمجي للمشروع:

- **Pyright (strict):** صفر أخطاء.
- **Ruff:** صفر أخطاء Style أو Bugs.
- **Pytest:** كل الاختبارات ناجحة بنسبة 100%.
- **Coverage:** لا تقل عن 80%.
- **Architecture:** لا توجد Circular Imports، ولا خرق لطبقات المشروع.
- **Type Safety:** لا يوجد `Any` غير مبرر، ولا تجاهل للأخطاء بـ `# type: ignore` إلا مع تعليق يوضح السبب. يُتحقق عبر `py -3.12 scripts/check_type_ignore.py` و`pyright`.
- **Security:** لا توجد أسرار (Secrets) داخل الكود، ولا استدعاءات غير آمنة.
- **Performance:** لا توجد عمليات مكلفة داخل حلقات متكررة دون داعٍ.

### 🚨 سياسة التراجع البرمجي وحراسة الدمج (Regression & CI/CD Gates Policy)

- **فشل الاختبارات حاط حظر كامل (Hard Blocking):** لا يُسمح بدمج أي كود أو التزام (Commit) إذا كان هناك اختبار واحد فاشل في `pytest` أو خطأ واحد في `pyright`.
- **التحقق التلقائي من الأزرار والـ Callbacks:** يُلزم تشغيل `scripts/validate_handlers.py` فور أي تغيير في ملفات `callback_constants.py` أو `keyboards.py` لمنع ظاهرة تجمد الأزرار قبل التدمير.
- **عزل التراجعات (Zero Regression Tolerance):** عند إصلاح أي استثناء شبكي، يجب عدم خرق التغطية القائمة أو تغيير سلوك الـ Mocks المعتمدة في مجلد `tests/`.

## CI/CD وعملية الإصدار

- **الbranch الرئيسي:** `main` هو branch الإنتاج.
- **التحقق قبل الدمج:** يجب أن تمر جميع أوامر Quality Gates المذكورة أعلاه.
- **ال版本:** يُستخدم \`semantic versioning\` عبر Git tags.
- **النشر:** يدوياً عبر سحب `main` على الخادم وإعادة تشغيل البوت.
- **النسخ الاحتياطي قبل التحديث:** يُنصح بعمل نسخة احتياطية يدوية قبل أي تحديث كبير.

قبل تشغيل `python main.py` (أو `py -3.12 main.py`) أو دمج أي تعديل، يُنصح بتنفيذ الأوامر التالية كحد أدنى:

```bash
py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"
ruff check .
py -3.12 scripts/validate_handlers.py
py -3.12 scripts/validate_routeros_paths.py
py -3.12 scripts/check_type_ignore.py
py -3.12 -m pyright
py -3.12 -m pytest --cov=bot --cov=core --cov=database --cov=utils --cov=pdf --cov-fail-under=80 -q
```

ملاحظات:

- `ruff check .` يستخدم الإعدادات من `ruff.toml` (قواعد E/F/W/I/UP/B).
- `validate_handlers.py` يتحقق من اتساق imports وتسجيل المعالجات؛ يتجاهل ثوابت ALL-CAPS (مثل `PATTERNS`, `CALLBACKS`) لأنها ليست معالجات.
- `validate_routeros_paths.py` يمنع hardcoded User Manager paths في `core/` لضمان توافق RouterOS v6/v7.
- `check_type_ignore.py` يتحقق من أن كل `# type: ignore` يحمل سبباً موثّقاً.
- `pyright` يستخدم `pyrightconfig.json` (وضع strict).
- `pytest` مهيأ في `pyproject.toml`. التغطية ≥ 80% مطلوبة (`--cov-fail-under=80`).
- عند تعديل Telegram flows، اختبر يدوياً من حساب مشرف داخل Telegram.

## المبادئ العامة وأسلوب العمل (دمج AI_DEVELOPMENT_GUIDE)

هذا القسم يدمج المبادئ السابقة الواردة في `AI_DEVELOPMENT_GUIDE.md` في مرجع واحد، ويحسم تعارض سياسة "User Approval" لصالح أسلوب `AGENTS.md` (التحليل ثم التنفيذ التلقائي مع الـ commit التلقائي). `AI_DEVELOPMENT_GUIDE.md` هو ملخص قديم؛ هذا القسم هو المرجع الموثوق.

### القاعدة الذهبية

- لا تكتب كوداً قبل أن تفهم المشكلة والملفات المتأثرة.
- لا تفترض إذا لم تكن متأكداً؛ اطلب الملف أو المعلومة الناقصة أولاً.
- مصدر الحقيقة الأول هو الكود الفعلي، لا التوثيق القديم.

### دورة العمل

أي مهمة تمر بالمراحل التالية بالترتيب:

1. **Analysis** — فهم المطلوب والملفات المتأثرة.
2. **Architecture Review** — فحص البنية الحالية وتأثير التغيير عليها.
3. **Risk Assessment** — تحديد المخاطر والأثر الجانبي على الوظائف القائمة.
4. **Implementation Plan** — خطة مختصرة (الملفات، DB، الخدمات).
5. **Implementation** — التنفيذ في دفعات صغيرة قابلة للمراجعة (مرحلة واحدة لكل طلب).
6. **Code Review** — فحص ذاتي لـ bugs/security/duplicate/dead code/races/perf/leaks.
7. **Testing** — خطة اختبار: حالات طبيعية + غير متوقعة + مدخلات خاطئة + regression.
8. **Documentation Update** — تحديث التوثيق المتأثر (بدون إنشاء وثائق غير مطلوبة).

### متى يُطلب الإذن (استثناء من التنفيذ التلقائي)

- **العمليات الجذرية التي لا رجعة فيها**: إعادة هيكلة المشروع بالكامل، تغيير أسماء ملفات أو دوال عامة، كسر Backward Compatibility، حذف وظيفة قائمة، أو قرار معماري عند تعدد الحلول. هذه تتطلب موافقة صريحة أو قراراً من المستخدم.
- **المهام العادية القابلة للتراجع**: تُنفَّذ تلقائياً مع الـ commit التلقائي دون طلب إذن مسبق.
- عند تعدد الحلول لقرار مؤثر، قدم مقارنة (مميزات/عيوب/أداء/صيانة/قابلية توسع) واترك القرار النهائي للمستخدم.

### أسلوب كتابة الكود

- Clean Architecture، SOLID، DRY، KISS، Separation of Concerns، Dependency Injection عند الحاجة.
- Repository Pattern للوصول للبيانات وService Layer لمنطق الأعمال.
- الـ Handlers خفيفة: استقبال + تحقق صلاحيات + استدعاء Service + إرسال النتيجة. لا Business Logic في handlers، ولا SQL مباشر.
- أي ميزة تندمج مع البنية الحالية؛ لا تنشئ ملفات أو مجلدات غير ضرورية.
- منطق RouterOS منفصل عن بقية المشروع؛ اختلاف v6/v7 داخل طبقة Adapter/Service (لا في handlers).
- أي Exception يُسجَّل في Logs، ويُرجع رسالة مناسبة للمستخدم، ولا يوقف البوت.

### مستوى الثقة

- إذا لم تكن متأكداً من استنتاجك، اذكر مستوى الثقة ولا تقدم افتراضات على أنها حقائق.

## ملاحظات صيانة معروفة

- ثوابت وأنماط `callback_data` مركزية في `bot/handlers/callback_constants.py` (`CALLBACKS`, البناة الديناميكية، `PATTERNS`). لا تكرر أنماطاً مضمّنة في `bot/registrations.py`؛ استخدم `PATTERNS["<name>"]`.
- حافظ على ترتيب callback patterns داخل `PATTERNS` من الأكثر تحديداً إلى الأعم عند وجود تعارض محتمل.
- كل start handler في flow جديد يجب أن ينظف الحالة القديمة عبر `cleanup_state()` ويضبط `nav_set()` عند الحاجة.
- لا تستخدم wildcard imports في handlers.
- راقب تضخم `context.user_data` وتأكد من إضافة المفاتيح المؤقتة إلى `cleanup_state()`.
- عند تعديل رسائل المستخدم، ضع النصوص في `bot/messages.py` لا داخل handlers إلا إذا كان النص داخلياً ومؤقتاً.
- إعدادات الـ logging تتم حصراً في `main.py` قبل `configure_logging()`؛ لا تضف `logging.basicConfig` جديد أو `setLevel` لمكتبات غير مزعجة.
- لا يوجد `HEALTH_CHECK_PORT` أو `aiohttp` في المشروع بعد الآن؛ تمت إزالة health check server بالكامل.
- `WATCHDOG_FIRST_DELAY` معرّف في `config.py:54` ويُستخدم في `bot/handlers/watchdog.py:67` كمهلة أولى للـ Job. لا تستخدم `first=10` مضمّناً.
- استخدم `sanitize_log_data()` من `utils/formatters.py` قبل تسجيل أي استجابة API في السجلات، خاصة عند مستوى `ERROR` أو `WARNING`.
- أزرار بداية التدفقات متعددة الخطوات (مثل `hotspot_add`، `hotspot_edit`، `hotspot_delete`، `hotspot_search`، `hotspot_cards`، `usage_start`، `batches_search`، `logs_filter_text`) تُسجَّل **حصراً** داخل الـ ConversationHandler الرئيسي كـ `entry_point` و`fallback` معاً في `bot/registration_parts/conversation.py`. **لا تُسجَّلها** كـ `@standalone(...)` في `bot/registration_parts/standalone.py` لأن `build_application()` في `utils/handler_registry.py` يضيف معالجات standalone قبل الـ main CH، فيبتلع بداية التدفق ويفكّك تتبع الـ conversation (كان هذا سبب خرق `e2e_smoke` خطوة 11b، وتم إصلاحه بإزالة 15 تسجيلاً standalone). الاستثناء الوحيد: callbacks التي تعمل خارج أي conversation (مثل `unblock_mac`).
- `usage_start` مُسجَّل كـ `entry_point(CallbackQueryHandler, ...)` و`fallback(...)` بجانب `CommandHandler` لأنه يُستدعى من زر في `bot/keyboards.py` ويبدأ تدفقاً متعدد الخطوات.
- يوجد استخدامات إنتاجية لـ `# type: ignore` في الكود: `core/connection_pool.py:101`, `core/mikrotik_api.py:217`, `bot/handlers/backup.py:82,83`, `bot/handlers/settings.py:181`, `utils/error_response.py:122`. جميعها مبررة ومعلّمة، ويُتحقق منها عبر `scripts/check_type_ignore.py`.
