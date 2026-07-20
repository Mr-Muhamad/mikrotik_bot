# خطة إعادة هيكلة SRP — MikroTik Telegram Bot

## الهدف
تفكيك المخالفات الأربع لمبدأ Single Responsibility Principle مع **الحفاظ الصارم** على:
- سلوك التشغيل الحالي (لا تغيير في UX أو ردود Telegram).
- واجهات الاستدعاء العامة (`hotspot_manager.<method>`, `build_all(application)`, دوال `common` المستوردة).
- بوابات الجودة: `ruff F821` ✅ + `validate_handlers.py` ✅ + `pytest` (808 unit) ✅ + E2E (15).

## القيد المعماري (من AGENTS.md)
- طبقة `core/` **يجب ألا تعتمد** على `telegram` أو `bot.`. أي استيراد من `core/` إلى `bot.messages`/`bot.keyboards` هو خرق يُزال.
- `ConversationHandler` الرئيسي يُسجَّل **قبل** standalone `cancel` (تحذير PTBUserWarning الحالي محمي بالاختبارات `test_registration_order.py`).
- `run_blocking()` يُستخدم لكل استدعاء `core/` متزامن من داخل handlers.
- `standalone(...)`/`fallback(...)` معرّفة في `utils/handler_registry.py` (وحدة قائمة بذاتها، لا تُعدّل). `build_all` يستدعيها فقط.

## حقائق مكتشفة (مثبّتة من الكود — لا تخمين)
- `bot/__init__.py` يستورد أسماء `common` **بالاسم الصريح** (أسطر 39–155). أي نقل دالة من `common.py` يستلزم تحديث سطر الاستيراد المقابل هناك، وإلا فشل import جماعي في كل الاختبارات.
- `hotspot_manager.create_cards` (سطر 446) يعتمد داخلياً على `self._get_existing_usernames`, `self.invalidate_users_cache`, `self.get_profiles` (كلها في نفس الصنف). تفكيك `create_cards` إلى وحدة أخرى يرفع المخاطرة بلا مكسب SRP واضح — بناء PDF نفسه موجود أصلاً في `pdf/`. **القرار:** إبقاء `create_cards` في الصنف.
- `registrations.py` لا يعرّف `standalone`/`fallback`؛ يستوردهما من `utils/handler_registry` (سطر 14–18). التفكيك يقتصر على توزيع أجسام الاستدعاءات داخل `build_all` على دوال مجال، مع الإبقاء على **ترتيب السطور الحالي حرفياً**.

---

## الملفات المستهدفة والاعتماديات المكتشفة

| الملف | الحجم | المشكلة | الاعتماد الخارجي الحرج |
|------|------|---------|------------------------|
| `bot/handlers/common.py` | 729 سطر / 44 دالة | God-object: واجهة + كشف شبكي + قوائم فرعية + أوامر | يُستورد فقط من `bot/__init__.py` (بالاسم) |
| `core/hotspot_manager.py` | 899 سطر / 32 دالة | CRUD + تقارير + إحصائيات + حظر MAC | يُستدعى عبر `run_blocking(hotspot_manager.X)` من 9 handlers |
| `bot/registrations.py` | 787 سطر / دالة واحدة `build_all` | كل التسجيلات في دالة عملاقة | يُستدعى من `main.py`/`e2e_smoke.py` عبر `build_all(application)` |
| `core/backup_scheduler.py:139` + `core/stats.py:103` | — | تسريب طبقات: `core` يستورد `bot.messages` | — |

---

## المهام (بالترتيب — كل خطوة مستقلة قابلة للاختبار)

### الخطوة 0 — إصلاح تسريب الطبقات (أقل مخاطرة، يمهد للباقي)
**ملفات:** `core/backup_scheduler.py`, `core/stats.py`, `bot/messages.py`
- `backup_scheduler.py:139` يستورد `EXPIRY_ALERT_HEADER`, `EXPIRY_ALERT_USER_ROW` من `bot.messages`.
  - الحل: نقل نصي التنبيه إلى `core/` (مثلاً `core/messages_expiry.py` جديد أو ثابت في `backup_scheduler` نفسه)، وترك `bot/messages.py` يستورد منه إن لزم العرض. **لا** يبقى استيراد `bot.` داخل `core/`.
- `core/stats.py:103` ("Format ... into an Arabic Telegram summary") — دالة تنسيق Telegram داخل core.
  - الحل: نقل دالة التنسيق إلى `bot/formatters.py` (أو `bot/handlers/`)؛ `stats.py` يبقى يُرجع dict خاماً فقط.
- **مخاطر:** منخفضة. خطر التحريك: نصوص التنبيه تظهر للمستخدم — تحقق عدم تغيير المحتوى العربي حرفياً.
- **سيناريو اختبار:** `py -3.12 -c "from core.backup_scheduler import ...; from core.stats import ..."` ثم `py -3.12 scripts/validate_handlers.py`.

### الخطوة 1 — تفكيك `core/hotspot_manager.py`
**القاعدة:** لا تغيير على أسماء/تواقيع `hotspot_manager.<method>` (لأن 9 handlers تعتمدها عبر `run_blocking`).
- أنشئ وحدات جديدة تحت `core/` مع **إعادة تصدير** من `hotspot_manager.py` (واجهة متوافقة):
  - `core/hotspot_stats.py` ← `get_hotspot_stats`, `build_usage_report`, `_parse_reset_day`, `_parse_uptime_to_seconds`. (`build_usage_report` يعتمد على `_get_leases_by_mac` سطر 289 — انقل الاعتمادية معها.)
  - `core/hotspot_blocking.py` ← `block_mac`, `unblock_mac`, `get_blocked_macs`.
  - `create_cards` **يُبقى** في `hotspot_manager` (يعتمد على `_get_existing_usernames`/`invalidate_users_cache`/`get_profiles` داخل الصنف).
  - `hotspot_manager.py` يُبقي: CRUD + cache + `create_cards` + `search_*` + `kick_*`. الوحدات الجديدة تُستورد ويُعاد تصديرها (`from core.hotspot_stats import ...`).
- **مخاطر:** متوسطة. `build_usage_report`/`get_hotspot_stats` قد تعتمدان على `_get_leases_by_mac`؛ تأكد نقل الاعتماديات الداخلية معها.
- **سيناريو اختبار:** `py -3.12 -m pytest tests/bot/handlers/test_hotspot_report.py tests/bot/handlers/test_hotspot_search.py tests/bot/handlers/test_hotspot_cards_handler.py -q`

### الخطوة 2 — تفكيك `bot/handlers/common.py`
أنشئ وحدات جديدة تحت `bot/handlers/` (كلها تستورد من `bot/__init__` آمنة):
- `bot/handlers/system_probe.py` ← `_get_router_system_part`, `_probe_path`, `_router_system_cache`, `context_user_data_get/set`. (منطق شبكي مكانه `core/` لكنه يعتمد `mikrotik_api` فقط — يمكن لاحقاً نقل الكشف لـ `core/router_info.py`؛ الآن نكتفي بفصله عن الواجهة.)
- `bot/handlers/menus.py` ← كل دوال `*_menu` + `_internal_*_menu` + `routers_menu`/`reports_menu` + `end_conversation_to_*`.
- `bot/handlers/commands_basic.py` ← `start`, `help_command`, `clean_chat`, `sync_commands`, `metrics_command`, `cancel`, `select_router_callback`, `error_handler`, `reprompt_*`.
- **`common.py` يُبقى كحاوية للدوال المساعدة المشتركة** (لا يُفرّغ): `_show_menu`, `_get_router_part`, `_resolve_nav_target`, `_end_conversation`, `go_back`. السبب: هذه الدوال تُستخدم من `menus.py` **و** `commands_basic.py` (دليل من الكود: `_show_menu` يُستدعى في 12 موقعاً عبر القوائم والأوامر)؛ وضعها في `common` يمنع دورة استيراد بين الوحدتين الجديدتين. **حقيقة مثبّتة:** لا توجد أي وحدة خارج `bot/__init__.py` تستورد من `common` — فالأسماء المنقولة (القوائم/الأوامر) تُضاف كاستيراد في `__init__.py`، والأسماء الباقية (المساعدة) تبقى في `common` كما هي.
- **مخاطر:** عالية. `bot/__init__.py` يستورد أسماء بالتحديد من `common` (أسطر 39–155) — عدّل الاستيراد там ليشير للوحدات الجديدة. أي اسم مفقود = خطأ import في كل الاختبارات.
- **سيناريو اختبار:** بعد كل نقل دالة، شغّل `py -3.12 -c "import bot"` (يفشل فوراً إن نُسي استيراد في `__init__.py`) ثم `py -3.12 scripts/validate_handlers.py`.

### الخطوة 3 — تفكيك `bot/registrations.py` (`build_all`)
قسّم `build_all` إلى دوال تجميع حسب المجال، مع **الحفاظ على ترتيب الاستدعاء الحالي**:
- `register_conversation_handlers(app)` (CH الرئيسي + CH المستقلة: rename, manual_add — تُسبق standalone cancel).
- `register_menu_handlers(app)`, `register_hotspot_handlers(app)`, `register_userman_handlers(app)`, `register_backup_handlers(app)`, `register_router_handlers(app)`, `register_reports_handlers(app)`, `register_misc_handlers(app)`.
- `build_all(application)` يستدعيها بالترتيب نفسه تماماً (لا تبديل مواقع السطور).
- **مخاطر:** عالية. تحذير `per_message=False` في `test_registration_order.py` يعتمد على ترتيب `rename_conv`/`manual_add_conv` قبل standalone cancel — لا تغيّر الترتيب. `standalone`/`fallback` من `utils/handler_registry` (لا تُعدّل).
- **سيناريو اختبار:** `py -3.12 -m pytest tests/test_registration_order.py -q` (يجب أن يبقى 3 passed بلا تحذير جديد عن الترتيب).

---

## مصفوفة المخاطر والتخفيف

| # | الخطر | الاحتمال | التخفيف |
|---|-------|---------|---------|
| R1 | كسر استيراد `bot/__init__.py` بسبب نقل أسماء من `common` | عالٍ | عدّل الاستيراد في `bot/__init__.py` ليشير للوحدات الجديدة؛ شغّل `validate_handlers.py` بعد كل خطوة |
| R2 | تغيير سلوك `build_usage_report`/`get_hotspot_stats` بسبب اعتماديات داخلية (`_get_leases_by_mac`) | متوسط | فحص imports داخل الدالة المنقولة؛ اختبار `test_hotspot_report.py` |
| R3 | تبدّل ترتيب تسجيل handlers يكسر `test_registration_order.py` | متوسط | لا تحرّك سطور `build_all`؛ فقط لُفها باستدعاءات دوال بنفس التسلسل |
| R4 | تغيير نصوص عربية للمستخدم (تنبيه انتهاء، تقارير) | منخفض | انسخ النصوص حرفياً؛ لا إعادة صياغة |
| R5 | تسريب اتصال MikroTik في `_probe_path` (كان يستخدم pool مباشرةً، صُحح لـ `mikrotik_api.execute`) | منخفض | `_probe_path` محمي بـ try/except و cached؛ لا يُستدعى إلا عند اختيار الراوتر |
| R6 | دورة import دائرية (common ← menus ← common) | متوسط | استوراد `bot/__init__` فقط في نقطة الدخول؛ داخل الوحدات استورد `telegram`/`core` مباشرة |

---

## خطة التحقق (بعد كل خطوة + نهائياً)
```
ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs --exclude _releases --exclude "scripts/Activate.ps1"
py -3.12 scripts/validate_handlers.py
py -3.12 -m pytest -q        # الهدف 808 passed
# E2E عند الإمكان: 15/15
```
- عدّادات التحقق تُشغَّل **بعد كل خطوة منفصلة** (ليس فقط في النهاية) لعزل أي انحدار.
- أي فشل في `validate_handlers` = استيراد/تسجيل مفقود ← يُعالج قبل المتابعة.

## الخطوات المفتوحة (خارج النطاق الحالي)
- نقل منطق الكشف `_probe_path`/الـ cache إلى `core/router_info.py` بشكل كامل (يُؤجل لتجنب مخاطرة إضافية).
- فصل `format_user` إن تبيّن استخدامه للعرض مقابل التقارير.

## التسليم
- Commit واحد لكل خطوة (حسب سياسة `git add . && git commit` في AGENTS.md) بعد نجاح البوابات.
- لا تعديل في `main.py` سوى إن لزم تحديث استيراد `build_all` (غير متوقع).
