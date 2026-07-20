# خطة تنفيذ المراجعة المعمارية الشاملة لمشروع Mikrotik Bot

## الهدف

تطبيق قائمة المراجعة المعمارية المكونة من 15 قسماً (في `review_rules.md` على المشروع بالكامل، وإخراج تقرير احترافي واحد `review_report.md` يحتوي على: ملخص تنفيذي، نقاط قوة/ضعف، مخاطر، ديون تقنية، خطة High-ROI، وتقييم نهائي بدرجة.

## مبادئ المراجعة (من review_rules.md)

- لا اقتراح Pattern إلا لحل مشكلة حقيقية موثقة من الكود.
- كل ملاحظة مدعومة بـ (اسم ملف:دالة/سطر) وسبب المشكلة والأثر العملي.
- إذا كان الكود جيداً، نذكره صراحة.
- فصل واضح بين: مشكلة حالية / تحسين مستقبلي / اقتراح اختياري.
- ممنوع إدخال تعقيد غير مبرر (No over-engineering).

## حالة المشروع (الاكتشاف)

- ~80+ ملف Python موزعة كالتالي:
  - `bot/handlers/` (32 ملف) — Handlers + flows + states + callback constants.
  - `bot/registration_parts/` (3 ملفات) — registration fragments.
  - `bot/` الجذر (keyboards, messages, profile_callbacks, router_selector).
  - `core/` (24 ملف) — Service layer (hotspot/userman/backup/profile/network/cache/metrics/...).
  - `database/repositories/` (11 ملف) — Repository Pattern مطبق.
  - `database/` الجذر (models.py + repositories/).
  - `utils/` (14 ملف) — Decorators, validators, crypto, logging, callbacks, pagination.
  - `pdf/` (3 ملفات) — card_renderer, pdf_renderer, card_generator.
  - `scripts/` (7 ملفات) — validate_handlers, snapshot_release, validate_routeros_paths, e2e_smoke, stress_test, helpers.
  - `tests/` (~50 ملف) — تغطية واسعة موجودة.
  - `docs/` (6 ملفات) — توجد مراجعات سابقة: `user_flow_and_smells_review.md`, `project-comparison-report.md`, `reconciliation-plan-vs-report.md` (يجب قراءتها كمدخلات لتجنب التكرار).
- أنماط معمارية ظاهرة سلفاً في الكود: Repository, Service Layer, Decorators, Connection Pool, Registry (callback_constants/PATTERNS), Facade (`core/backup_service.py` فوق `core/backup/`).
- Branch نشط: `ivory-kepler` (worktree). الفرع الأساسي `main`.

## المخرج النهائي

ملف واحد: `D:\New Projects 21-5\Mikrotik admin bot telegram\mikrotik_bot\review_report.md`

**بنية التقرير** (مطابقة لـ review_rules.md):

1. ملخص تنفيذي (Executive Summary) — 5–10 أسطر + التقييم النهائي بدرجة.
2. نقاط القوة (Bullet list مع أدلة).
3. نقاط الضعف (Bullet list مع أدلة وأولوية).
4. المراجعة التفصيلية (الأقسام 1–14 من الـ checklist، كل قسم بجدول `البند | الحالة | الدليل | الأولوية | يستحق التنفيذ الآن؟`).
5. جدول المخاطر (القسم 10).
6. الديون التقنية (القسم 11).
7. سجل القرارات المؤجلة (القسم 12).
8. ما لا يجب تغييره (القسم 13).
9. جدول الأولويات النهائية High-ROI (القسم 14): `التحسين | الفائدة | تكلفة التنفيذ | الأولوية`.
10. تقييم نهائي بدرجة (A+, A, B+, B, C) مع تبرير.

## استراتيجية التنفيذ على مراحل

التقسيم يضمن أن كل مرحلة مستقلة، وأن المراحل المبكرة تنتج حقائق تستفيد منها المراحل اللاحقة. كل مرحلة تخرج بـ `phase_N_outline.md` يحتوي على النقاط المرشحة فقط (بدون كتابة review_report.md النهائي).

---

### المرحلة 0 — التحضير ومدخلات المشروع

**الهدف:** تأسيس قاعدة حقائق من وثائق المشروع السابقة.

**الملفات المطلوب قراءتها (بالتوازي):**

- `AGENTS.md` — الدستور الحالي.
- `PROJECT_OVERVIEW.md`, `PROJECT_WORKFLOW_BASELINE.md`, `FEATURES_MANIFEST.md`.
- `docs/user_flow_and_smells_review.md` — مراجعة سابقة للـ UX والـ smells.
- `docs/project-comparison-report.md`, `docs/reconciliation-plan-vs-report.md`.
- `docs/routeros-v6-v7-compatibility.md`, `docs/routeros-api-security.md`.
- `docs/post-plan-best-practices.md`, `docs/priority-plan.md`.
- `.plans/*.md` — كل الخطط السابقة لتجنب تكرار العمل.

**المخرج:** ملف `review/phase_0_context.md` يحتوي على:
- قائمة الـ patterns المطبقة فعلياً (مع أدلة).
- قائمة الـ smells المعروفة سابقاً (لتجنب تكرارها).
- قائمة الأنماط المؤجلة (DI, Strategy, PostgreSQL, Circuit Breaker).
- قائمة الـ commands والـ callbacks والـ states (مأخوذة من `utils/bot_commands.py` و`bot/handlers/callback_constants.py`).

**شرط الانتقال:** قراءة كاملة لـ `phase_0_context.md` قبل بدء المرحلة 1.

---

### المرحلة 1 — مراجعة معمارية + جودة الكود (الأقسام 1, 6)

**الهدف:** الحكم على البنية الداخلية وجودة الكود (مكونات ثابتة نسبياً).

**الملفات الحرجة للإجابة على أسئلة القسم 1 (Architecture):**

- Facade: `core/backup_service.py`, `bot/handlers/routers.py` (re-export) — هل الـ interface ضيّق ومستقر؟
- Repository: `database/repositories/*.py` + `database/models.py`.
- Service Layer: `core/hotspot_manager.py`, `core/userman_manager.py`, `core/backup/*.py`, `core/network_scanner.py`.
- Decorators: `utils/admin_decorator.py`, `utils/error_response.py`, `utils/async_blocking.py`.
- State Machine: `bot/handlers/states.py`, `bot/registrations.py`, `bot/registration_parts/conversation.py`, `bot/registration_parts/standalone.py`, `bot/registration_parts/separate_handlers.py`.
- Connection Pool: `core/connection_pool.py`.
- Registry: `bot/handlers/callback_constants.py` (CALLBACKS, builders, PATTERNS).
- DI: فحص constructor signatures عبر `core/` و`database/`.
- Strategy: البحث عن `if version == "v6"` في `core/` و`bot/`.
- SoC/HighCohesion/LowCoupling: فحص اعتماد `bot/` على `database/` مباشرة، و`core/` على `telegram`.

**الملفات الحرجة للقسم 6 (Code Quality):**

- `pyrightconfig.json` + `pyproject.toml` + `ruff.toml`.
- تشغيل: `ruff check . --select F821 --exclude venv,backups,logs,_releases,__pycache__`.
- تشغيل: `py -3.12 -m pytest -q --collect-only` لمعرفة عدد الاختبارات الفعلي.
- فحص Dead Code: ابحث عن functions غير مستدعاة عبر Grep.
- فحص Circular Imports: `python -c "import ast; ..."` أو يدوي عبر تتبع imports في `bot/__init__.py` و`bot/handlers/__init__.py`.
- Magic Strings: قارن `CALLBACKS` في `callback_constants.py` مع النصوص المضمّنة في handlers.
- Long Functions / Fat Controllers: عد أسطر أي دالة > 80 سطر.

**المخرج:** ملف `review/phase_1_architecture_code_quality.md`.

**شرط الانتقال:** قائمة أولويات واضحة لمشكلات المعمارية وجودة الكود.

---

### المرحلة 2 — رحلة المستخدم + سيناريوهات الأخطاء + الأداء (الأقسام 2, 3, 4)

**الهدف:** الحكم على تجربة المستخدم، المتانة، والأداء.

**القسم 2 (User Flow) — الملفات:**

- `bot/handlers/common.py`, `bot/handlers/menus.py`, `bot/handlers/commands_basic.py`.
- `bot/handlers/router_system.py` + `bot/handlers/router_flows/*.py`.
- `bot/handlers/hotspot_add.py`, `hotspot_edit.py`, `hotspot_delete.py`, `hotspot_cards.py`, `hotspot_search.py`, `hotspot_report.py`.
- `bot/handlers/userman.py`, `userman_search.py`.
- `bot/handlers/backup.py`, `backup_restore.py`, `settings.py`.
- `bot/keyboards.py`, `bot/messages.py`, `bot/router_selector.py`, `bot/profile_callbacks.py`.
- `bot/handlers/timeout.py` (Conversation Timeout).
- `bot/handlers/handler_utils.py`, `bot/handlers/hotspot_common.py`, `bot/handlers/hotspot_flow_utils.py`.
- `bot/handlers/session_models.py`.
- `bot/registration_parts/*.py`.

**للتحقق من:** بداية واضحة، اختيار الراوتر (مرة واحدة)، زر رجوع، إلغاء، conversation timeout، رسائل "جاري التنفيذ..."، حماية من ضياع الحالة.

**القسم 3 (Failure Scenarios):**

- offline router / timeout / wrong creds: `core/mikrotik_client.py`, `core/mikrotik_api.py`, `core/connection_pool.py`, `utils/error_response.py`, `core/exceptions.py`.
- حذف أثناء الفتح / stale data: مسارات edit/delete في handlers + repositories.
- ضغط متكرر: `utils/callback_utils.py` (`is_duplicate_callback`), `bot/handlers/callback_constants.py`.
- conversation timeout: `bot/handlers/timeout.py`.
- رسائل أخطاء مفهومة: بحث في `bot/messages.py` عن قاموس الأخطاء.

**القسم 4 (Performance):**

- `core/connection_pool.py` — إعدادات pool size, timeouts, retry/throttle.
- `utils/async_blocking.py` — `run_blocking`.
- `database/models.py` — schema, indexes, مزامنة SQLite في عمليات async.
- `utils/pagination.py` — هل مطبّق؟
- `core/cache.py`, `core/profile_cache.py` — TTL caches.
- `utils/pagination.py` + البحث عن pagination في handlers.
- العمليات الثقيلة: backup/restore في `core/backup/*.py`, card generation في `pdf/card_generator.py`.

**المخرج:** ملف `review/phase_2_ux_errors_performance.md`.

**شرط الانتقال:** قائمة مشاكل تجربة المستخدم والأخطاء الحرجة.

---

### المرحلة 3 — الأمان + التشغيل + قابلية التوسع والامتداد + المخرجات النهائية (الأقسام 5, 7, 8, 9, 10, 11, 12, 13, 14)

**الهدف:** إغلاق المراجعة وكتابة `review_report.md`.

**القسم 5 (Security):**

- `utils/admin_decorator.py` — `@admin_only`, `@require_router`, rate limit.
- `config.py` — تحميل `BOT_TOKEN`, `ADMIN_IDS`, `ENCRYPTION_KEY`.
- `utils/crypto.py` + `database/models.py` (decrypt_password).
- `utils/validators.py`.
- `database/repositories/operator_permissions.py`, `admin_roles.py`.
- `utils/logging_setup.py` — هل تتسرب أسرار في logs؟
- `core/mikrotik_client.py` — تنفيذ أوامر بدون router context؟

**القسم 7 (Scalability):**

- `core/connection_pool.py` — حدود pool.
- `database/models.py` — حدود SQLite (single-writer, file lock).
- `utils/singleton_lock.py` — منع تشغيل متعدد.
- `core/backup_scheduler.py` + `core/connection_pool.py`.
- سيناريوهات: N routers × M admins × K users في وقت واحد.

**القسم 8 (Extensibility):**

- بنية `bot/handlers/` و`core/` — هل يمكن إضافة handlers جديدة بسهولة؟
- `bot/registrations.py` — هل تسجيل handler جديد يتطلب تعديل 5 ملفات؟
- `core/backup/` — Facade pattern يبسّط الإضافة.

**القسم 9 (Operational):**

- `main.py` — init_db, post_init, polling, graceful shutdown.
- `core/backup_scheduler.py` — جدولة النسخ.
- `core/watchdog.py` + `bot/handlers/watchdog.py`.
- `utils/logging_setup.py` — request_id, file/console handlers.
- `core/metrics.py` + `/metrics`.
- `bot/handlers/audit.py` + `database/repositories/audit_logs.py` — سجل التدقيق.

**المخرج النهائي:** كتابة `review_report.md` كاملاً في جذر المشروع.

---

## أدوات التحقق المطلوبة (يُشغّلها الـ Agent المنفّذ)

```bash
# 1. إحصائيات الكود
wc -l bot/**/*.py core/*.py database/repositories/*.py utils/*.py

# 2. Pyright (strict)
py -3.12 -m pyright

# 3. Ruff
ruff check . --exclude venv,backups,logs,_releases,__pycache__

# 4. Validate handlers
py -3.12 scripts/validate_handlers.py

# 5. Pytest (نظرة عامة)
py -3.12 -m pytest -q --co 2>&1 | tail -5

# 6. الاستيراد (دخان)
py -3.12 -c "import main"
```

> ملاحظة: `py -3.12 -m pytest -q` كاملاً غير مطلوب في المراجعة. يكفي `--collect-only` للعدد + تشغيل الاختبارات الحرجة فقط إذا لزم.

---

## قواعد الـ Agent المنفّذ

- **لا تعدّل كوداً.** هذه مراجعة، ليس refactor.
- اكتب ملفات `review/phase_*.md` المؤقتة و `review_report.md` النهائية فقط.
- عند ذكر أي مشكلة: اسم ملف + دالة/سطر + سبب + أثر عملي.
- لا تخمّن — إذا لم تجد دليلاً، اذكر "غير مؤكد يحتاج تحقق".
- عند الحكم "جيد": وضّح لماذا هو جيد (دليل إيجابي).
- إذا كانت مراجعة سابقة في `docs/` تتعارض مع ما تراه في الكود: الكود هو مصدر الحقيقة.

---

## Acceptance Criteria (معايير النجاح)

- ✅ `review_report.md` يحتوي على جميع الأقسام الـ 15.
- ✅ كل بند في الجداول مربوط بـ (ملف:دالة أو ملف:سطر).
- ✅ جدول المخاطر مكتمل (اسم/احتمال/تأثير/أولوية/معالجة) ولا يقل عن 5 مخاطر.
- ✅ جدول High-ROI لا يقل عن 5 تحسينات، مرتبة تنازلياً.
- ✅ التقييم النهائي بدرجة (A+/A/B+/...) مع تبرير موجز.
- ✅ قسم "ما لا يجب تغييره" لا يقل عن 4 عناصر.
- ✅ لا بند "Pattern لمجرد أنه Pattern" — كل اقتراح يحل مشكلة موثقة.

---

## Out of Scope (ما لن تشمله المراجعة)

- تنفيذ أي refactor أو إصلاح (المراجعة تقرير فقط).
- كتابة اختبارات جديدة.
- ترقية dependencies أو تحديث Python.
- تصميم UI/UX بصري (الرسومات، الـ themes) — فقط الـ flow النصي.

---

## Risks للـ Review نفسه (ما يجب مراقبته)

- **استهلاك Tokens:** قراءة ~80 ملف في مرحلة واحدة قد يضغط السياق. الحل: المراحل الثلاث + قراءة موجهة بقوائم Grep قبل الـ Read الكامل.
- **تضارب مع المراجعات السابقة:** `docs/user_flow_and_smells_review.md` و `docs/project-comparison-report.md` بهما ملاحظات قديمة. الأولوية للكود الحالي.
- **تقييم متحيز:** الـ Agent يجب أن يكون صريحاً مع نفسه — إذا كان الوضع جيداً، يقول ذلك.

---

## نقطة البداية للـ Agent المنفّذ

ابدأ بـ:

1. اقرأ `AGENTS.md` و`PROJECT_OVERVIEW.md` (5 دقائق).
2. اقرأ `docs/user_flow_and_smells_review.md` و`docs/project-comparison-report.md` (لاحظ التاريخ).
3. اقرأ `review/phase_0_context.md` لو كان موجوداً من تنفيذ سابق.
4. شغّل أدوات التحقق الست أعلاه واحفظ النتائج.
5. ابدأ المرحلة 1 بقراءة الملفات الحرجة للقسمين 1 و 6 بالتوازي.