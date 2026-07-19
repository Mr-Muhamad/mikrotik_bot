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
- قاعدة بيانات متطورة تدار عبر `Alembic` لدعم ترقيات المخططات مستقبلاً بأمان.

## المتطلبات

- Python 3.10+.
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

`main.py` يقوم بتهيئة قاعدة البيانات (مع تشغيل ترقيات Alembic بشكل آلي)، بناء تطبيق Telegram، تسجيل المعالجات من `bot/registrations.py`، ضبط أوامر Telegram من `utils/bot_commands.py`، استعادة جدولة النسخ الاحتياطي، وتشغيل watchdog مع graceful shutdown عبر signal handlers.

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
| `/settings` | إعدادات PDF. |
| `/reboot` | إعادة تشغيل الراوتر المختار. |
| `/timeout` | إعداد مدة الخمول وحماية الجلسة. |
| `/metrics` | عرض أداء الاتصالات وحالة استهلاك السيرفر (CPU/RAM). |
| `/logs` | عرض سجل التدقيق. |
| `/sync` | إعادة ضبط قائمة الأوامر السريعة. |
| `/clean` | تنظيف رسائل الشات المتتبعة. |
| `/usage` | تقرير استخدام مستخدم Hotspot. |
| `/watchdog` | عرض حالة مراقبة الروترات. |
| `/watchdog_start` | بدء مراقبة الروترات. |
| `/cancel` | إلغاء المحادثة الحالية. |

## هيكل المشروع المختصر

```text
mikrotik_bot/
├── main.py                    # نقطة تشغيل البوت
├── config.py                  # تحميل .env والتحقق من الإعدادات المطلوبة
├── utils/
│   ├── registrations.py       # التسجيل المركزي للمعالجات
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
│   ├── singleton_lock.py      # منع أكثر من نسخة بوت
│   └── validators.py          # التحقق من المدخلات
├── bot/
│   ├── handlers/              # معالجات Telegram لكل feature
│   │   ├── common.py          # القوائم والأوامر العامة
│   │   ├── routers.py         # واجهة توافق لتدفقات الروترات
│   │   ├── router_flows/      # discover, saved, rename, reboot flows
│   │   ├── hotspot_*.py       # Hotspot add/edit/delete/search/cards
│   │   ├── hotspot_flow_utils.py # أدوات مساعدة مشتركة محدودة لبعض تدفقات Hotspot
│   │   ├── session_models.py  # نماذج بيانات قوية (Dataclasses) لبيانات المحادثات
│   │   ├── userman.py         # User Manager
│   │   ├── userman_search.py  # البحث عن مستخدمي User Manager
│   │   ├── backup.py          # النسخ الاحتياطي والجدولة
│   │   ├── backup_restore.py  # الاستعادة
│   │   ├── stats.py           # الإحصائيات
│   │   ├── settings.py        # إعدادات PDF
│   │   ├── audit.py           # سجل التدقيق
│   │   ├── usage.py           # تقرير الاستخدام
│   │   └── watchdog.py        # مراقبة الروترات
│   ├── helpers/profiles.py    # جلب وكاش البروفايلات
│   ├── keyboards.py           # أزرار InlineKeyboard
│   ├── messages.py            # مركز النصوص العربية والرسائل
│   └── router_selector.py     # حالة الراوتر والجلسة
├── core/
│   ├── mikrotik_api.py        # تنفيذ أوامر RouterOS
│   ├── connection_pool.py     # إدارة اتصالات MikroTik
│   ├── hotspot_manager.py     # منطق Hotspot
│   ├── userman_manager.py     # منطق User Manager
│   ├── backup_service.py      # واجهة توافق لخدمات backup/restore
│   ├── backup/                # تنفيذ backup وrestore بعد التقسيم
│   │   ├── files.py           # أدوات المسارات الآمنة والتنظيف
│   │   ├── system.py          # منطق system backup
│   │   ├── userman.py         # منطق User Manager backup/restore
│   │   └── restore.py         # استعادة النسخ المحلية
│   ├── backup_scheduler.py    # جدولة النسخ
│   ├── network_probe.py       # MNDP/ARP/port scan
│   ├── network_scanner.py     # اكتشاف الروترات
│   ├── profile_cache.py       # TTL cache للبروفايلات
│   ├── profile_sync.py        # جلب بروفايلات User Manager
│   ├── stats.py               # إحصائيات عامة
│   └── watchdog.py            # فحص صحة الراوترات
├── database/                  # قواعد البيانات
│   ├── models.py              # النماذج وعمليات CRUD
│   └── alembic/               # ترقيات المخطط (Migrations)
├── alembic.ini                # إعدادات أداة Alembic
├── pdf/                       # توليد PDF للكروت
├── scripts/                   # أدوات التحقق والإصدار
└── tests/                     # اختبارات pytest
```

## المعمارية

- يعتمد البوت على `python-telegram-bot` و`ConversationHandler` لتدفقات المحادثة متعددة الخطوات، مدعوماً بنماذج بيانات `Dataclasses` لضمان النوعية (`Type Safety`).
- التسجيل الفعلي للمعالجات موجود في `bot/registrations.py`.
- `utils/handler_registry.py` يبني `ConversationHandler` الرئيسي، ويدعم أيضاً `ConversationHandler`ات مستقلة لبعض التدفقات.
- `concurrent_updates(False)` مفعل لضمان استقرار FSM.
- عمليات MikroTik المتزامنة يتم تنفيذها عبر `run_blocking()` حتى لا يتم حجب event loop.
- اتصال MikroTik يمر عبر `core/mikrotik_api.py` و`core/connection_pool.py` مع retry وtimeouts وrate limiting.
- `bot/handlers/routers.py` واجهة توافق؛ التنفيذ الفعلي لتدفقات الروترات موزع داخل `bot/handlers/router_flows/`.
- `core/backup_service.py` واجهة توافق؛ التنفيذ الفعلي للنسخ الاحتياطي والاستعادة موزع داخل `core/backup/`.
- البيانات المحلية تحفظ في SQLite داخل `mikrotik_bot.db`.
- النسخ الاحتياطية تحفظ داخل `backups/`.
- إدارة السجلات تتم عبر `utils/logging_setup.py`؛ الشاشة تظهر `INFO` فما فوق، والملف `logs/mikrotik-bot.log` يسجل `DEBUG` فما فوق بتنسيق JSON مع `request_id` لكل عملية.

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
ruff check . --select F821
py -3.12 scripts/validate_handlers.py
py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"
py -3.12 -m pytest -q
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
2. سجله في `utils/registrations.py` كـ `standalone`, `entry_point`, `state`, أو `fallback` حسب الحاجة.
3. أضفه إلى `utils/bot_commands.py` حتى يظهر في قائمة `/`.
4. أضف وصفه إلى `HELP` في `bot/messages.py` إذا كان موجهاً للمستخدم.
5. شغّل `python scripts/validate_handlers.py` وQuality Gates كاملة.
