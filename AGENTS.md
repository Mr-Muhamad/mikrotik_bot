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

- `BOT_TOKEN`: توكن Telegram Bot.
- `ADMIN_IDS`: معرفات مشرفي Telegram مفصولة بفواصل.
- `ENCRYPTION_KEY`: مفتاح Fernet صالح ومطلوب فعلياً. `config.py` يوقف التشغيل إذا كان المفتاح مفقوداً أو قصيراً.

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
│   ├── singleton_lock.py      # منع تشغيل أكثر من نسخة بوت
│   └── validators.py          # التحقق من المدخلات
├── bot/
│   ├── registrations.py       # التسجيل المركزي للأوامر، callbacks، states، fallbacks (المسار الفعلي: bot/registrations.py)
│   ├── handlers/
│   │   ├── common.py          # /start, /help, /clean, /metrics, /sync والقوائم
│   │   ├── routers.py         # واجهة توافق لتدفقات إدارة الروترات
│   │   ├── router_flows/      # discover, saved, rename, reboot flows
│   │   ├── hotspot_add.py     # إضافة مستخدم Hotspot
│   │   ├── hotspot_edit.py    # تعديل مستخدم Hotspot
│   │   ├── hotspot_delete.py  # حذف مستخدم Hotspot
│   │   ├── hotspot_search.py  # بحث وطرد hosts
│   │   ├── hotspot_cards.py   # إنشاء كروت Hotspot PDF
│   │   ├── hotspot_flow_utils.py # أدوات مساعدة مشتركة محدودة لتدفقات Hotspot
│   │   ├── hotspot.py         # إحصائيات Hotspot التفصيلية
│   │   ├── userman.py         # User Manager cards/list/profiles
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
│   ├── helpers/profiles.py    # جلب وتخزين أسماء البروفايلات مؤقتاً
│   ├── keyboards.py           # كل InlineKeyboard builders
│   ├── messages.py            # النصوص العربية للمستخدم
│   ├── profile_callbacks.py   # callback index cache للبروفايلات
│   └── router_selector.py     # الراوتر المختار وحالة التنقل لكل مستخدم
├── core/
│   ├── mikrotik_api.py        # واجهة تنفيذ لأوامر RouterOS مع retry/throttle
│   ├── connection_pool.py     # connection pool وtimeouts وmetrics
│   ├── hotspot_manager.py     # Hotspot CRUD/search/kick/cards
│   ├── userman_manager.py     # User Manager cards/list
│   ├── backup_service.py      # واجهة توافق لخدمات backup/restore
│   ├── backup/
│   │   ├── files.py           # أدوات آمنة للمسارات والتنظيف والتحقق
│   │   ├── system.py          # منطق system backup
│   │   ├── userman.py         # منطق User Manager backup/restore
│   │   └── restore.py         # استعادة system backups المحلية
│   ├── backup_scheduler.py    # جدولة النسخ اليومي عبر JobQueue
│   ├── network_probe.py       # MNDP/ARP/port scan primitives
│   ├── network_scanner.py     # discovery orchestrator
│   ├── profile_cache.py       # TTL cache للبروفايلات
│   ├── profile_sync.py        # جلب User Manager profiles
│   ├── stats.py               # إحصائيات عامة
│   ├── router_key.py          # helper لمفاتيح discovered routers
│   └── watchdog.py            # health status in-memory
├── database/models.py         # SQLite schema, CRUD, migrations خفيفة
├── pdf/                       # PDF generation باستخدام reportlab وqrcode ودعم العربية
├── scripts/                   # validate_handlers, snapshot_release, logging audit helper
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
- `/metrics` - أداء الاتصالات.
- `/logs` - سجل التدقيق.
- `/sync` - إعادة ضبط قائمة الأوامر السريعة.
- `/clean` - تنظيف الشات.
- `/usage` - تقرير استخدام مستخدم.
- `/watchdog` - حالة مراقبة الروترات.
- `/watchdog_start` - بدء مراقبة الروترات.
- `/cancel` - إلغاء المحادثة الحالية.

## إضافة أمر جديد

عند إضافة أمر جديد `/xyz`، حدّث هذه المواضع:

1. إنشاء handler في ملف مناسب داخل `bot/handlers/` مع `@admin_only` عند الحاجة.
2. تصدير handler من `bot/handlers/__init__.py` إذا كان نمط المشروع الحالي يحتاجه.
3. استيراد وتسجيل handler في `bot/registrations.py` باستخدام `standalone`, `entry_point`, `state`, أو `fallback` حسب نوع الأمر. إن احتاج الأمر `callback_data` جديداً، عرّفه في `bot/handlers/callback_constants.py` (`CALLBACKS` أو أحد البناة) وأضف نمطه إلى `PATTERNS`، ثم استخدم `PATTERNS["<name>"]` في التسجيل.
4. إضافة الأمر إلى `utils/bot_commands.py` حتى يظهر في قائمة `/` داخل Telegram.
5. تحديث `HELP` في `bot/messages.py` إذا كان الأمر موجهاً للمستخدم.
6. تشغيل `python scripts/validate_handlers.py` بعد التعديل.

ملاحظة: لا تضف تسجيل المعالجات مباشرة إلى `main.py` إلا إذا كان هناك سبب معماري واضح. المسار الحالي هو `utils/registrations.py`.

## قواعد مهمة في MikroTik API

- مفتاح الراوتر المحفوظ يأخذ الشكل `discovered_{db_id}`.
- المنفذ الافتراضي لخدمة API هو `8728` من `config.DEFAULT_API_PORT`.
- `ip/hotspot/host/print` لا يحتوي دائماً على `host-name`؛ يتم إثراؤه من DHCP leases بالـ MAC.
- `ip/hotspot/active/print` يستخدم في عمليات طرد المستخدمين النشطين.
- `reset-counters` يستخدم `numbers=` وليس `.id`.
- مسار User Manager يختلف بين RouterOS v6 وv7، ويحدد عبر `mikrotik_api.get_userman_base_path()`.
- كاش الإصدار (`router_versions`) له صلاحية 24 ساعة؛ بعد ترقية RouterOS أو إعادة تسمية الراوتر نادِ `mikrotik_api.invalidate_version(router_key)` لإبطال الكاش وإعادة اختيار المسار الصحيح. المرجع الكامل في `docs/routeros-v6-v7-compatibility.md`.
- استخدم `execute_long()` للعمليات الثقيلة مثل backup أو جلب قوائم كبيرة.

## قواعد الأمان

- `BOT_TOKEN`, `ADMIN_IDS`, و`ENCRYPTION_KEY` مطلوبة في `config.py`.
- اتصال MikroTik API على المنفذ `8728` غير مشفّر؛ شغّل البوت داخل شبكة إدارة معزولة وقيّد خدمة `api` على IP جهاز البوت. التفاصيل في `docs/routeros-api-security.md`. لا تُفرض API-SSL أو REST كمسار أساسي لأن الراوترات قد لا تملك شهادة SSL ولا يغطي REST إصدار v6 جيداً.
- لا تحفظ أو تعرض كلمات المرور في logs أو رسائل Telegram.
- `update_pdf_settings()` يستخدم whitelist للأعمدة؛ لا تبن SQL ديناميكياً خارج هذا النمط.
- `decrypt_password()` (معرّفة في `utils/crypto.py` وتُعاد تصديرها عبر `database/models.py`) يعيد نصاً فارغاً عند فشل الفك ولا تعيد ciphertext.
- استخدم `is_duplicate_callback()` في callbacks التي قد تؤدي إلى عمليات خطرة أو مزدوجة مثل reboot وbackup.
- لا ترفع `.env`, `mikrotik_bot.db`, `logs/`, `venv/`, أو محتويات `backups/` إلى Git (مستثناة في `.gitignore`).

## Quality Gates

قبل تشغيل `python main.py` (أو `py -3.12 main.py`) بعد أي تعديل، نفذ:

```bash
ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs --exclude _releases --exclude "scripts/Activate.ps1"
py -3.12 scripts/validate_handlers.py
py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"
py -3.12 -m pytest -q
```

ملاحظات:

- `ruff check . --select F821` يركز على الأسماء غير المعرفة.
- `scripts/validate_handlers.py` يتحقق من اتساق imports وتسجيل المعالجات؛ يتجاهل ثوابت ALL-CAPS (مثل `PATTERNS`, `CALLBACKS`) لأنها ليست معالجات.
- `pytest` مهيأ في `pyproject.toml` ويستخدم مجلد `tests`.
- عند تعديل Telegram flows، اختبر يدوياً من حساب مشرف داخل Telegram.

## ملاحظات صيانة معروفة

- ثوابت وأنماط `callback_data` مركزية في `bot/handlers/callback_constants.py` (`CALLBACKS`, البناة الديناميكية، `PATTERNS`). لا تكرر أنماطاً مضمّنة في `bot/registrations.py`؛ استخدم `PATTERNS["<name>"]`.
- حافظ على ترتيب callback patterns داخل `PATTERNS` من الأكثر تحديداً إلى الأعم عند وجود تعارض محتمل.
- كل start handler في flow جديد يجب أن ينظف الحالة القديمة عبر `cleanup_state()` ويضبط `nav_set()` عند الحاجة.
- لا تستخدم wildcard imports في handlers.
- راقب تضخم `context.user_data` وتأكد من إضافة المفاتيح المؤقتة إلى `cleanup_state()`.
- عند تعديل رسائل المستخدم، ضع النصوص في `bot/messages.py` لا داخل handlers إلا إذا كان النص داخلياً ومؤقتاً.
- إعدادات الـ logging تتم حصراً في `main.py` قبل `configure_logging()`؛ لا تضف `logging.basicConfig` جديد أو `setLevel` لمكتبات غير مزعجة.
- لا يوجد `HEALTH_CHECK_PORT` أو `aiohttp` في المشروع بعد الآن؛ تمت إزالة health check server بالكامل.
