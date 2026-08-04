# MikroTik Telegram Bot

بوت Telegram عربي لإدارة روترات MikroTik RouterOS. يدعم إدارة Hotspot، User Manager، اكتشاف الروترات، النسخ الاحتياطي، الإحصائيات، إعدادات PDF، مراقبة حالة الروترات، وسجل التدقيق.

## الميزات

- اكتشاف روترات MikroTik على الشبكة عبر MNDP وحفظها محلياً.
- اختيار راوتر نشط لكل مشرف وحفظ الاختيار في SQLite.
- إدارة مستخدمي Hotspot: إضافة، تعديل، حذف، بحث، طرد أجهزة، وتقرير استخدام.
- دعم عرض القوائم الطويلة (Pagination) في الكروت، وعمليات البحث و User Manager.
- إنشاء كروت Hotspot عشوائية وإرسال PDF جاهز للطباعة.
- إدارة User Manager: إنشاء كروت، عرض المستخدمين، جلب البروفايلات.
- نسخ احتياطي يدوي للنظام وUser Manager، وجدولة نسخ يومية عبر JobQueue.
- استعادة نسخ system backup واستعادة User Manager من ملفات محلية.
- إعدادات PDF قابلة للتعديل من Telegram، مع دعم العربية وQR Code.
- مراقبة حالة الروترات عبر watchdog وتنبيه المشرفين عند الانقطاع والعودة.
- حماية الجلسات الذكية: فصل الراوتر المختار تلقائياً عند الخمول للحماية (مع أمر `/timeout` لتخصيص المدة).
- سجل تدقيق `/logs` للعمليات المهمة.
- تشفير كلمات مرور الروترات المحفوظة باستخدام Fernet.
- حماية إدارية عبر `ADMIN_IDS`، rate limit، deduplication للـ callbacks، وتعقيم للأخطاء الحساسة.
- نماذج بيانات محكمة (Typed Dataclasses) لإدارة تدفق المحادثات بشكل آمن.

## المتطلبات

- Python 3.10+ (مُطوَّر ومُختبَر على Python 3.12).
- تفعيل خدمة MikroTik API على الراوتر: `IP -> Services -> api`.
- المنفذ الافتراضي لخدمة API هو `8728` (من `config.DEFAULT_API_PORT`).
- **تنبيه**: اتصال `8728` غير مشفّر (نصّي/ثنائي) ويعمل عبر `librouteros`. يجب تشغيله داخل شبكة موثوقة ومقيدة فقط. راجع ضوابط التخفيف في `docs/routeros-api-security.md`.
- حساب MikroTik **مخصص ومحدود الصلاحيات** للبوت (ليس `admin` العام)، وله صلاحيات كافية لإدارة Hotspot/User Manager والنسخ الاحتياطي.

## التثبيت

```bash
cd mikrotik_bot
pip install -r requirements.txt
cp .env.example .env
```

لبيئة التطوير وتشغيل الاختبارات:

```bash
pip install -r requirements-dev.txt
```

> **بيئة Python**: إذا كان `python` يشير إلى مسار معطوب (مثل `venv` يشير إلى Python غير موجود، أو تداخل `WindowsApps`/`uv`)، استخدم مفسّر النظام الصريح:
> `py -3.12 -m pip install -r requirements.txt` و`py -3.12 main.py`.
> كل فحوص الجودة أدناه تُشغَّل بنفس الطريقة (`py -3.12 ...`).

عدّل ملف `.env`:

| المتغير | الوصف |
|---|---|
| `BOT_TOKEN` | توكن البوت من BotFather. |
| `ADMIN_IDS` | معرفات مشرفي Telegram مفصولة بفواصل. |
| `ENCRYPTION_KEY` | مفتاح Fernet مطلوب لتشفير كلمات مرور الروترات. |

توليد `ENCRYPTION_KEY` صالح:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ملاحظة: `config.py` يوقف تشغيل البوت إذا كان `BOT_TOKEN`, `ADMIN_IDS`, أو `ENCRYPTION_KEY` مفقوداً. لا تعتمد على fallback مؤقت في بيئة التشغيل.

## التشغيل

```bash
python main.py
```

`main.py` يقوم بتهيئة قاعدة البيانات، بناء تطبيق Telegram، تسجيل المعالجات من `bot/registrations.py`، ضبط أوامر Telegram من `utils/bot_commands.py`، استعادة جدولة النسخ الاحتياطي، وتشغيل watchdog مع graceful shutdown عبر signal handlers.

## الأوامر

| الأمر | الوظيفة |
|---|---|
| `/start` | القائمة الرئيسية واختيار الراوتر. |
| `/help` | عرض المساعدة. |
| `/add` | إضافة مستخدم Hotspot. |
| `/edit` | تعديل مستخدم Hotspot. |
| `/delete` | حذف مستخدم Hotspot. |
| `/search` | البحث عن مستخدم أو جهاز Hotspot. |
| `/cards` | إنشاء كروت Hotspot وإرسال PDF. |
| `/userman` | إنشاء كروت User Manager. |
| `/backup` | فتح قائمة النسخ الاحتياطي. |
| `/routers` | إدارة الروترات المحفوظة. |
| `/addrouter` | إضافة روتر يدوياً (IP/منفذ/مستخدم/كلمة مرور/اسم). |
| `/settings` | إعدادات PDF. |
| `/reboot` | إعادة تشغيل الراوتر المختار. |
| `/timeout` | إعداد مدة الخمول وحماية الجلسة. |
| `/metrics` | عرض مقاييس Prometheus (أداء الاتصالات، صحة المكونات، معدل الأخطاء) وحالة استهلاك السيرفر (CPU/RAM). |
| `/logs` | عرض سجل التدقيق. |
| `/sync` | إعادة ضبط قائمة الأوامر السريعة. |
| `/clean` | تنظيف رسائل الشات المتتبعة. |
| `/usage` | تقرير استخدام مستخدم Hotspot. |
| `/watchdog` | عرض حالة مراقبة الروترات. |
| `/watchdog_start` | بدء مراقبة الروترات. |
| `/cancel` | إلغاء المحادثة الحالية. |
| `/reports` | التقارير. |
| `/report` | تقرير المبيعات. |
| `/roles` | إدارة أدوار المشرفين. |
| `/batches` | دفعات الكروت. |
| `/sales` | المبيعات. |
| `/add_customer` | إضافة عميل. |
| `/remove_customer` | إزالة عميل. |

## هيكل المشروع المختصر

```text
mikrotik_bot/
├── main.py                    # نقطة تشغيل البوت
├── config.py                  # تحميل .env والتحقق من الإعدادات المطلوبة
├── alembic.ini                # إعداد Alembic والاتصال بـ SQLite
├── alembic/                   # Alembic migrations (الترحيلات)
├── docs/                      # توثيق أمني وتوافق (routeros-api-security, routeros-v6-v7-compatibility)
├── utils/
│   ├── handler_registry.py    # بناء ConversationHandler والمعالجات المستقلة
│   ├── bot_commands.py        # أوامر Telegram السريعة
│   ├── admin_decorator.py     # حماية المشرف واختيار الراوتر
│   ├── async_blocking.py      # تشغيل العمليات المتزامنة في executor
│   ├── callback_utils.py      # callback answer وdeduplication
│   ├── chat_cleaner.py        # تتبع وتنظيف الرسائل
│   ├── crypto.py              # تشفير كلمات المرور
│   ├── error_response.py      # رسائل أخطاء آمنة
│   ├── formatters.py          # تنسيق bytes وتعقيم API responses
│   ├── logging_setup.py       # request_id logging
│   ├── log_helpers.py         # log_api_call لتسجيل وتوقيت استدعاءات API الخارجية
│   ├── pagination.py          # أدوات الترقيم للقوائم
│   ├── request_id.py          # تتبع request_id عبر ContextVar
│   ├── singleton_lock.py      # منع أكثر من نسخة بوت
│   ├── tg_helpers.py          # دوال مساعدة لـ Telegram
│   └── validators.py          # التحقق من المدخلات
├── bot/
│   ├── __init__.py            # حزمة bot
│   ├── registrations.py       # التسجيل المركزي للمعالجات
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
│   │   ├── routers.py         # واجهة توافق لتدفقات الروترات
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
│   │   ├── userman.py         # User Manager
│   │   ├── userman_search.py  # البحث عن مستخدمي User Manager
│   │   ├── backup.py          # النسخ الاحتياطي والجدولة
│   │   ├── backup_restore.py  # الاستعادة
│   │   ├── stats.py           # الإحصائيات
│   │   ├── settings.py        # إعدادات PDF
│   │   ├── audit.py           # سجل التدقيق
│   │   ├── usage.py           # تقرير الاستخدام
│   │   ├── watchdog.py        # مراقبة الروترات
│   │   ├── states.py          # WaitingState enum
│   │   ├── callback_constants.py # ثوابت callback_data وأنماط PATTERNS
│   │   ├── constants.py       # WAITING_* constants
│   │   └── router_flows/
│   │       ├── __init__.py    # إعادة تصدير تدفقات الروترات
│   │       ├── discovery.py   # اكتشاف الروترات
│   │       ├── manual_add.py  # إضافة روتر يدوياً مع التحقق
│   │       ├── reboot.py      # إعادة تشغيل الراوتر
│   │       ├── rename.py      # إعادة تسمية الراوتر
│   │       └── saved.py       # الروترات المحفوظة
│   ├── helpers/profiles.py    # جلب وكاش البروفايلات
│   ├── keyboards/             # أزرار InlineKeyboard (حزمة)
│   │   ├── __init__.py        # إعادة تصدير مختارة للتوافق مع الاختبارات
│   │   ├── common.py          # أزرار القوائم الرئيسية والتنقل
│   │   ├── hotspot.py         # أزرار Hotspot
│   │   ├── operator.py        # أزرار المشغّلين
│   │   ├── reports.py         # أزرار التقارير والسجلات
│   │   ├── router.py          # أزرار الروترات
│   │   ├── settings.py        # أزرار إعدادات PDF
│   │   └── userman.py         # أزرار User Manager
│   ├── messages.py            # مركز النصوص العربية والرسائل
│   ├── profile_callbacks.py   # callback index cache للبروفايلات
│   └── router_selector.py     # حالة الراوتر والجلسة
├── core/
│   ├── __init__.py            # حزمة core
│   ├── mikrotik_api.py        # تنفيذ أوامر RouterOS
│   ├── mikrotik_client.py     # MikroTik client wrapper
│   ├── connection_pool.py     # إدارة اتصالات MikroTik
│   ├── circuit_breaker.py     # فاصل الدارة (circuit breaker) لطلبات MikroTik API
│   ├── cache.py               # TTLCache عام (dict-based مع threading.Lock)
│   ├── exceptions.py          # فئات الاستثناءات المخصصة
│   ├── metrics.py             # مقاييس Prometheus: record_action, record_error, record_component_result, record_db_query, record_mikrotik_request, record_telegram_request, get_health_status
│   ├── hotspot_manager.py     # منطق Hotspot
│   ├── hotspot_blocking.py    # حظر/فك حظر MAC عبر address-list
│   ├── hotspot_expiry.py      # كشف المستخدمين المنتهيين
│   ├── hotspot_search.py      # بحث المضيفين وإثراء DHCP leases وطرد
│   ├── hotspot_stats.py       # إحصائيات Hotspot مع تصفية يوم إعادة الضبط
│   ├── userman_manager.py     # منطق User Manager
│   ├── backup_service.py      # واجهة توافق لخدمات backup/restore
│   ├── backup/
│   │   ├── __init__.py        # حزمة backup
│   │   ├── files.py           # أدوات المسارات الآمنة والتنظيف
│   │   ├── file_server.py     # خادم ملفات لتخزين النسخ الاحتياطية
│   │   ├── ftp.py             # رفع/تحميل عبر FTP
│   │   ├── system.py          # منطق system backup
│   │   ├── userman.py         # منطق User Manager backup/restore
│   │   └── restore.py         # استعادة النسخ المحلية
│   ├── backup_scheduler.py    # جدولة النسخ
│   ├── network_probe.py       # MNDP/ARP/port scan
│   ├── network_scanner.py     # اكتشاف الروترات
│   ├── profile_cache.py       # TTL cache للبروفايلات
│   ├── profile_sync.py        # جلب بروفايلات User Manager
│   ├── messages_expiry.py     # إدارة انتهاء صلاحية الرسائل
│   ├── card_models.py         # نماذج بيانات الكروت
│   ├── chart_generator.py     # إنشاء الرسوم البيانية للتقارير
│   ├── reports_excel.py       # إنشاء تقارير Excel
│   ├── reports_export.py      # وظائف التصدير
│   ├── router_info.py         # مساعدات معلومات الروتر
│   ├── stats.py               # إحصائيات عامة
│   ├── router_key.py          # helper لمفاتيح discovered routers
│   └── watchdog.py            # فحص صحة الراوترات
├── database/
│   ├── __init__.py            # حزمة database
│   ├── models.py              # النماذج وعمليات CRUD
│   ├── execute.py             # timed_execute — توقيت وتتبع استعلامات DB مع record_db_query
│   └── repositories/          # مستودعات البيانات (CRUD)
│       ├── admin_roles.py     # إدارة أدوار المشرفين
│       ├── audit_logs.py      # سجلات التدقيق والتنظيف
│       ├── backups.py         # مهام وإعدادات النسخ الاحتياطي
│       ├── card_batches.py    # دفعات الكروت وملخص المبيعات
│       ├── chat_messages.py   # الرسائل المتعقبة
│       ├── operator_permissions.py # أذونات المشغّل
│       ├── pdf_settings.py    # إعدادات PDF
│       ├── routers.py         # الروترات المكتشفة CRUD
│       ├── router_health.py   # سجل صحة الروترات
│       ├── stats_snapshots.py # لقطات الإحصائيات
│       └── user_sessions.py   # جلسات المستخدمين وتتبع النشاط
├── pdf/                       # توليد PDF للكروت
│   ├── __init__.py            # حزمة pdf
│   ├── card_generator.py      # منطق إنشاء الكروت
│   ├── card_renderer.py       # عرض الكروت
│   ├── pdf_renderer.py        # عرض PDF
│   └── pdf_settings.py        # إعدادات PDF
├── scripts/                   # أدوات التحقق والإصدار
└── tests/                     # اختبارات pytest
    ├── stress/                # اختبارات تزامن حتمية (time.monotonic patch-leak hang)
    └── fault/                 # حقن أعطال (circuit-breaker, DB latency, FTP, RouterOS)
```

## المعمارية

- يعتمد البوت على `python-telegram-bot` و`ConversationHandler` لتدفقات المحادثة متعددة الخطوات، مدعوماً بنماذج بيانات `Dataclasses` لضمان النوعية (`Type Safety`).
- التسجيل الفعلي للمعالجات موجود في `bot/registrations.py`، ومقسم إلى `bot/registration_parts/` (conversation / separate_handlers / standalone).
- `utils/handler_registry.py` يبني `ConversationHandler` الرئيسي، ويدعم أيضاً `ConversationHandler`ات مستقلة لبعض التدفقات.
- `concurrent_updates(False)` مفعل لضمان استقرار FSM.
- عمليات MikroTik المتزامنة يتم تنفيذها عبر `run_blocking()` حتى لا يتم حجب event loop.
- اتصال MikroTik يمر عبر `core/mikrotik_api.py` و`core/connection_pool.py` مع retry وtimeouts وrate limiting، ويحميه `core/circuit_breaker.py` من فشل متسلسل.
- `bot/handlers/routers.py` واجهة توافق؛ التنفيذ الفعلي لتدفقات الروترات موزع داخل `bot/handlers/router_flows/`.
- `core/backup_service.py` واجهة توافق؛ التنفيذ الفعلي للنسخ الاحتياطي والاستعادة موزع داخل `core/backup/`.
- البيانات المحلية تحفظ في SQLite داخل `mikrotik_bot.db` مع ترحيلات Alembic في `alembic/`.
- النسخ الاحتياطية تحفظ داخل `backups/`.
- إدارة السجلات تتم عبر `utils/logging_setup.py`؛ الشاشة تظهر `INFO` فما فوق، والملف `logs/mikrotik-bot.log` يسجل `DEBUG` فما فوق بتنسيق JSON مع `request_id` لكل عملية.
- مقاييس Prometheus متاحة عبر `core/metrics.py` وتُصدَر عبر `/metrics` (أداء الاتصالات، صحة المكونات، معدل الخطأ، استهلاك السيرفر).

## التبعيات

التبعيات الأساسية موجودة في `requirements.txt`:

```text
python-telegram-bot>=21.0
librouteros>=3.3.0
python-dotenv>=1.0.0
reportlab>=4.0
cryptography>=41.0
qrcode>=7.0
arabic-reshaper>=3.0.0
python-bidi>=0.4.0
alembic>=1.13.1
sqlalchemy>=2.0.0
ruff>=0.3.0
```

المشروع يحتوي اختبارات `pytest` ومهيأ عبر `pyproject.toml` لاستخدام مجلد `tests`.
تبعيات التطوير والفحص موجودة في `requirements-dev.txt`.

## ملاحظات أمنية

- **اتصال API غير مشفّر**: المنفذ `8728` ينقل بيانات الإدارة (بما فيها بيانات اعتماد الراوتر) دون تشفير. شغّل البوت داخل شبكة إدارة معزولة، وقيّد خدمة `api` على IP جهاز البوت، وامنع الوصول من WAN. التفاصيل في `docs/routeros-api-security.md`.
- لا ترفع `.env` أو `mikrotik_bot.db` أو محتويات `backups/` أو `logs/` أو `venv/` إلى Git. هذه المسارات مستثناة أصلاً في `.gitignore`؛ تأكد من تهيئة المستودع (`git init`) حتى يُطبَّق الاستثناء، خصوصاً أن المشروع قد لا يكون مستودعاً بعد.
- `ENCRYPTION_KEY` مطلوب حتى تبقى كلمات مرور الروترات قابلة للفك بعد إعادة التشغيل.
- فقط المستخدمون الموجودون في `ADMIN_IDS` يمكنهم استخدام البوت.
- رسائل الأخطاء يجب أن تبقى آمنة ولا تعرض كلمات مرور أو توكنات.
- يفضل تشغيل البوت من بيئة مستقرة بصلاحيات مناسبة لاكتشاف MNDP عند الحاجة.

## التحقق بعد التعديل

قبل تشغيل البوت بعد أي تعديل (استخدم `py -3.12` بدل `python` عند الحاجة):

```bash
py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"
ruff check .
py -3.12 scripts/validate_handlers.py
py -3.12 scripts/validate_routeros_paths.py
py -3.12 scripts/check_type_ignore.py
py -3.12 -m pyright --pythonpath ".\venv\Scripts\python.exe"
py -3.12 -m pytest --cov=bot --cov=core --cov=database --cov=utils --cov=pdf --cov-fail-under=80 -q
```

ثم شغّل البوت:

```bash
py -3.12 main.py
```

اختبر يدوياً من حساب مشرف:

- `/start`
- اختيار أو اكتشاف راوتر.
- قائمة Hotspot.
- قائمة User Manager.
- قائمة Backup.
- `/metrics`
- `/logs`
- `/watchdog`

## إضافة أمر جديد

عند إضافة أمر جديد:

1. اكتب handler داخل `bot/handlers/` مع `@admin_only` إذا كان موجهاً للمشرفين.
2. سجله في `bot/registrations.py` كـ `standalone`, `entry_point`, `state`, أو `fallback` حسب الحاجة.
3. أضفه إلى `utils/bot_commands.py` حتى يظهر في قائمة `/`.
4. أضف وصفه إلى `HELP` في `bot/messages.py` إذا كان موجهاً للمستخدم.
5. شغّل `python scripts/validate_handlers.py` وQuality Gates كاملة.
