# تقرير المراجعة المعمارية الشاملة — MikroTik Telegram Admin Bot

> **نطاق المراجعة:** مراجعة فقط (لا تغييرات كود). كل استنتاج مدعوم بدليل `ملف:دالة:سطر` حقيقي من الكود الحالي.
> **تاريخ التقرير:** 2026-07-20
> **الدرجة النهائية:** **B+**

---

## 1. مراجعة البنية المعمارية (Architecture)

### 1.1 Facade Pattern — ✅ مطبّق بشكل صحيح
- **الدليل:** `core/mikrotik_api.py:23-394` — `class MikrotikAPI` يطبّق بروتوكول `MikrotikClient` ويتبع واجهة موحّدة: `execute`, `execute_long`, `execute_non_blocking`, `test_connection`.
- **الأثر:** يخفي تعقيد `ConnectionPool` وإعادة المحاولة و throttle عن بقية النظام.
- **التوصية:** لا تغيير. حافظ على هذه الواجهة كعقد ثابت.

### 1.2 Repository Pattern — ✅ مطبّق بشكل جيد
- **الدليل:** `database/repositories/` يحتوي على: `routers.py`, `user_sessions.py`, `card_batches.py`, `audit_logs.py`, `backups.py`, `pdf_settings.py`, `router_health.py`, `admin_roles.py`, `chat_messages.py`. كل repository مسؤول عن جدول واحد.
- **الأثر:** فصل واضح وسهل الاختبار.
- **التوصية:** إزالة تدريجية لـ re-export shim في `database/models.py` (انظر 11.1) — لا يؤثر على السلوك.

### 1.3 Service Layer — ✅ مطبّق بشكل صحيح
- **الدليل:** `core/backup_service.py:18-46` — `BackupService` Facade فوق `core/backup/system.py` و `core/backup/userman.py`.
- **التوصية:** لا تغيير.

### 1.4 Decorators — ✅ مطبّق بشكل صحيح
- **الدليل:** `utils/admin_decorator.py:82-163` — `@admin_only` يحقق `ADMIN_IDS` ثم دور المستخدم؛ `@require_role("admin")` يطبّق مستوى صلاحية.
- **ملاحظة:** `RATE_LIMIT_WINDOW = 1.0` (`utils/admin_decorator.py:31`) — نافذة 1 ثانية قد تكون ضيّقة لعمليات بطيئة متكررة من نفس المشرف.
- **التوصية:** لا تغيير جوهري؛ راقب false-positive من rate limit تحت الاستخدام الكثيف.

### 1.5 State Machine — ✅ منظم
- **الدليل:** `bot/handlers/states.py` — `WaitingState` enum به **41 حالة** (INPUT, USERNAME, PASSWORD, PROFILE, CARD_COUNT, CARD_PAYMENT, HOTSPOT_CARD_COUNT, …). `utils/handler_registry.py:263` يضبط `conversation_timeout=300` (5 دقائق).
- **الأثر:** 41 حالة تغطي كل التدفقات الفرعية؛ الـ timeout يمنع الجلسات العالقة.
- **التوصية:** مقبول. عند إضافة ميزة جديدة، أضف حالة واحدة فقط (لا توسّع بلا مبرم).

### 1.6 Connection Pool — ✅✅ ممتاز
- **الدليل:** `core/connection_pool.py:17-22` — `MAX_RETRIES=2`, `CONNECT_TIMEOUT=10`, `API_TIMEOUT=30`, `LONG_TIMEOUT=120`, `MAX_CONNECTIONS_PER_ROUTER=3`. طابور `queue.Queue(maxsize=3)` لكل راوتر (`connection_pool.py:109,178`). كاش أسماء/إصدارات TTL 24 ساعة.
- **الأثر:** يمنع استنزاف الاتصالات ويحدّ من التزامن لكل راوتر.
- **التوصية:** **لا تغيير — هذا أفضل جزء في النظام.**

### 1.7 Registry Pattern — ✅ مطبّق بشكل صحيح
- **الدليل:** `utils/handler_registry.py:48-295` — تسجيل مركزي (entry_points, states, fallbacks, standalone, groups). `_build_handler:220-228` يغلّف كل handler بـ `bind_request_id_from_update` و `navigation_guard` عند الحاجة.
- **الأثر:** مصدر حقيقة واحد لترتيب التسجيل، يمنع أخطاء precedence.
- **التوصية:** لا تغيير.

### 1.8 Dependency Injection — ⚠️ حقن يدوي موجود، لا إطار
- **الدليل:** `core/backup_service.py:19-25` يقبل `system_service`/`userman_service` اختيارياً؛ `core/userman_manager.py:39-47` يقبل `api`.
- **الأثر:** يكفي للمقياس الحالي ويسمح باختبار وحدوي.
- **التوصية:** لا حاجة لإطار DI.

### 1.9 Strategy Pattern — ⚠️ منطق شرطي v6/v7
- **الدليل:** `core/userman_manager.py:168-202` — `_attach_v7_profile` vs `_attach_v6_profile` بناءً على `base_path`. التفرّع مكرّر في `mikrotik_api.get_userman_base_path`.
- **الأثر:** يعمل لكنه مكرّر.
- **التوصية:** حُوّل إلى Strategy فقط لو زادت الفروع خارج v6/v7.

### 1.10 Separation of Concerns — ✅ جيد
- طبقات `bot/` (UI) ⇄ `core/` (منطق بلا Telegram) ⇄ `database/` (وصول بيانات) ⇄ `utils/` (مساعدات).

### 1.11 High Cohesion / 1.12 Low Coupling — ✅ جيد مع ملاحظة
- ملاحظة: `database/models.py` re-export shim يخلق coupling غير ضروري (انظر 11.1).

---

## 2. مراجعة رحلة المستخدم (User Flow)

| الجانب | الحالة | الدليل | التوصية |
|---|---|---|---|
| بداية الاستخدام | ✅ | `/start` يعرض القائمة الرئيسية | لا تغيير |
| اختيار الراوتر | ⚠️ | `bot/router_selector.py:186-230` — `get_selected_router` يتحقق من session timeout | أضف زر "تغيير الراوتر" داخل القائمة الرئيسية |
| التنقل (back) | ✅ | أزرار `go_back`/`cancel`، `nav_set`/`nav_get` يديران back stack | لا تغيير |
| المحادثات | ✅ | `conversation_timeout=300` (`handler_registry.py:263`) | لا تغيير |
| العمليات الطويلة | ⚠️ | `userman.py` يرسل `CREATING_CARDS` قبل `run_blocking`؛ `reboot.py:65` يرسل `REBOOT_IN_PROGRESS` | أضف مؤشر تحميل لـ `list_users` والبحث |
| دقة الراوتر | ✅ | `_fast_reachability_check` (`router_selector.py:318-324`) | لا تغيير |

---

## 3. مراجعة سيناريوهات الأخطاء (Failure Scenarios)

| السيناريو | الحالة | الدليل | التوصية |
|---|---|---|---|
| انقطاع الاتصال | ✅✅ | `mikrotik_api.py:182-209` retry + `force_reconnect`؛ `connection_pool.py:78-100` `_connect_with_retry` | لا تغيير |
| راوتر offline | ✅ | `_fast_reachability_check` | لا تغيير |
| بيانات دخول خاطئة | ✅ | `_classify_connect_failure` (`mikrotik_api.py:313-369`) | لا تغيير |
| تنفيذ مزدوج | ✅ | `is_duplicate_callback` (`callback_utils.py:18-36`) — نافذة 1 ثانية | لا تغيير |
| ترك المحادثة وعودة متأخرة | ✅ | timeout 300s + فحص `session_timeout` | لا تغيير |
| عرض الخطأ للمستخدم | ✅ | `send_error` (`error_response.py:110-179`) يصنّف ويعرض رسالة عربية | لا تغيير |
| reboot يفقد الاتصال | ✅ (متعمد) | `reboot.py:76-84` يلتقط كل الاستثناءات ويعرض نجاح | موثّق بصيغة تعليق عربي واضح — لا تغيير |

**استنتاج:** معالجة الأخطاء من أقوى نقاط النظام. لا إصلاح مطلوب.

---

## 4. مراجعة الأداء (Performance)

| العنصر | الحالة | الدليل | التوصية |
|---|---|---|---|
| Connection Pool | ✅✅ | `connection_pool.py:22` `MAX=3` + كاش TTL | لا تغيير |
| Thread Pool | ⚠️ **مرشّح للإصلاح** | `async_blocking.py:18` `ThreadPoolExecutor(max_workers=50)` | **قلّله إلى 10–15** |
| Async | ✅ | كل handlers async؛ `run_blocking` مع `contextvars.copy_context()` | لا تغيير |
| SQLite | ⚠️ | `models.py:33-36` `timeout=10`, `WAL`, `busy_timeout=5000` | راقب `SQLITE_BUSY`؛ PostgreSQL لو زادت الكتابات المتزامنة >5 |
| Pagination | ❌ **ناقص** | `userman_manager.py:320-334` `list_users` يجلب **الكل** ثم `normalized[:limit]` | **طبّق pagination على مستوى API** |
| العمليات الثقيلة | ✅ | `execute_long` مع `LONG_TIMEOUT=120` | لا تغيير |

**أولوية الإصلاح:** تقليل ThreadPool + Pagination (انظر 14).

---

## 5. مراجعة الأمان (Security)

| الجانب | الحالة | الدليل | التوصية |
|---|---|---|---|
| صلاحيات | ✅ | `@admin_only`, `@require_role`, `ROLE_LEVELS` | لا تغيير |
| تحقق من المدخلات | ✅ | `validators.py` يُستدعى في `hotspot_add.py:87-90` | لا تغيير |
| تخزين كلمات المرور | ✅✅ | `encrypt_password` (`routers.py:40`) بـ Fernet؛ `migrate_passwords` (`models.py:103-123`) | لا تغيير |
| تشفير | ✅✅ | `utils/crypto.py` Fernet | لا تغيير |
| إخفاء الأسرار في السجلات | ✅✅ | `_debug_log` يخفي كلمات المرور (`mikrotik_api.py:172-176`)؛ `_sanitize_error_text`/`_SECRET_PATTERNS` (`error_response.py:30-66`) | لا تغيير |
| منع عمليات بلا راوتر | ⚠️ | `navigation_guard` يُطبّق عبر `_build_handler:224-226` لـ operational handlers فقط | تحقق من تسجيل كل operational handler عبر registry |

**استنتاج:** الأمان من أقوى نقاط النظام. الإصلاح الوحيد المقترح: ضمان تغطية `navigation_guard` الكاملة.

---

## 6. مراجعة جودة الكود (Code Quality)

| الأداة/الجانب | الحالة | الدليل | التوصية |
|---|---|---|---|
| Ruff (F821 undefined) | ✅ | `ruff check . --select F821` → "All checks passed!" | لا تغيير |
| Ruff (E501 line-too-long) | ⚠️ | 9 أسطر فقط مع `# noqa: E501` في ملفات re-export/helper | لا تغيير (مقبول) |
| Pyright | ❌ **غير مثبت** | `pyrightconfig.json` موجود لكن `report*` كلها `"none"` و pyright غير منفّذ | **ثبّت pyright وفعّل strict في CI** |
| Type Hints | ✅ | معظم الدوال مُحاضَرة | لا تغيير |
| Dead Code | ✅ | لم يُعثر على دوال/متغيرات غير مستخدمة | لا تغيير |
| Duplicate Code | ⚠️ | `reboot.py:69-84` يكرّر كود تعديل الرسالة مرتين | استخرج دالة مساعدة |
| Long Functions | ⚠️ | `userman.py` دوال طويلة؛ `userman_manager.create_cards` ~75 سطر | قسّم إلى دوال أصغر |
| Magic Strings | ✅ | مركزية في `callback_constants.py` (`CALLBACKS`, `PATTERNS`) | لا تغيير |
| Circular Imports | ✅ | imports داخلية آمنة | لا تغيير |

**أولوية الإصلاح:** تثبيت pyright (انظر 14).

---

## 7. مراجعة قابلية التوسع (Scalability)

| المحور | الحالة | التوصية |
|---|---|---|
| زيادة الراوترات | ✅ | Pool مستقل per-router — لا إجراء |
| زيادة المشرفين | ✅ | أدوار في DB — لا إجراء |
| زيادة المستخدمين | ⚠️ | راقب `busy_timeout`؛ PostgreSQL لو الكتابات المتزامنة >5 |
| زيادة العمليات المتزامنة | ⚠️ | قلّل `max_workers=50` → 10–15 (انظر 4، 14) |
| callback_data (Telegram 64 بايت) | ⚠️ | راجع `callback_constants.py` لضمان عدم التجاوز |

---

## 8. مراجعة قابلية الامتداد (Extensibility)

- **إضافة ميزة:** تتطلب 4 تعديلات — `WaitingState` (states.py) + `CALLBACKS`/`PATTERNS` (callback_constants.py) + `registrations.py` + `messages.py`. إجراء معروف لكنه متعدد الملفات.
- **إضافة نوع راوتر (PPPoE/WireGuard):** ممكن لكن بجهد — يلمس `mikrotik_api.py` و `userman_manager.py`.
- **التوصية:** لا إعادة هيكلة الآن؛ حافظ على العقد الحالية.

---

## 9. مراجعة التشغيل (Operational)

| الجانب | الحالة | الدليل |
|---|---|---|
| Logging | ✅✅ | `logging_setup.py` منظم + `request_id` عبر `bind_request_id_from_update` |
| Metrics | ✅ | `get_metrics()` (`connection_pool.py:243-258`)؛ `get_cleanup_stats()` (`chat_cleaner.py:337-339`) |
| Health Check | ✅ | `router_health` repo؛ `check_connection_health` (`mikrotik_api.py:132-143`) |
| Graceful Shutdown | ⚠️ | `mikrotik_api.close()` يغلق الاتصالات؛ لكن لا يوجد تطبيق صريح في `main.py` |

**التوصية:** أضف `application.create_task(...)` صريح لإغلاق الـ pool عند `SIGINT/SIGTERM`.

---

## 10. مراجعة المخاطر (Risk Table)

| الخطر | الاحتمالية | التأثير | الأولوية | المعالجة |
|---|---|---|---|---|
| SQLite busy timeout تحت حمل عالي | Medium | High | Medium | راقب؛ PostgreSQL لو الكتابات >5 متزامنة |
| ThreadPool exhaustion (50 worker) | Medium | Medium | **High** | قلّل إلى 10–15 |
| `context.user_data` نمو غير محدود | Low | Medium | Low | أضف cleanup دوري |
| تجاوز `callback_data` 64 بايت | Low | Medium | Low | راجع `callback_constants.py` |
| `pyright` غير مثبت | High | Low | **High** | ثبّت وأضف لـ CI |
| `navigation_guard` غير متسق | Medium | Medium | Medium | تحقق من تغطية registry |
| كود مكرّر في `reboot.py` | Low | Low | Low | استخرج دالة |

---

## 11. مراجعة الديون التقنية (Technical Debt)

### 11.1 يجب تحسينه (High ROI)
1. **إزالة `database/models.py` re-export shim** — يعمل لكنه يخلق coupling غير مبرر. الإزالة تدريجية عبر تحديث الاستيرادات إلى `database/repositories/*`.
2. **تقليل `ThreadPoolExecutor(max_workers=50)`** → 10–15 (`async_blocking.py:18`).
3. **تثبيت `pyright`** وفعّل strict في CI رغم وجود `pyrightconfig.json`.

### 11.2 يمكن تأجيله (Medium)
1. **Pagination على مستوى API** في `userman_manager.list_users` (حالياً يجلب الكل ثم يقطع).
2. **تقسيم دوال `userman.py` الطويلة** — تعمل بشكل صحيح لكن صيانتها أصعب.

### 11.3 لا يستحق التعديل الآن
1. **Connection Pool design** — ممتاز كما هو.
2. **Repository Pattern** — فصل جيد.
3. **SQLite** — مناسب لمقياس Admin Bot.

---

## 12. مراجعة القرارات المعمارية (Decision Log)

| القرار | الحالة | السبب |
|---|---|---|
| SQLite بدل PostgreSQL | متعمد | مقياس Admin Bot لا يتطلب DB مركزي؛ WAL+BUSY_TIMEOUT كافية |
| لا إطار DI | متعمد | حجم المشروع لا يستحق التعقيد؛ حقن يدوي في النقاط الحرجة كافٍ |
| لا Circuit Breaker | متعمد | `ConnectionPool` + retry + `NON_RETRYABLE_ERRORS` يكفي |
| لا Async RouterOS lib | متعمد | `librouteros` غير async؛ `run_blocking` هو الحل الواقعي |
| `contextvars.copy_context()` | متعمد | نقل `request_id` للخيوط دون تعقيد |

---

## 13. ما الذي لا يجب تغييره؟ (What Not To Change)

1. **Connection Pool** (`core/connection_pool.py`) — تصميم ممتاز بطوابير per-router وإعادة محاولة ذكية وكاش TTL.
2. **Repository Pattern** — فصل واضح للمسؤوليات.
3. **SQLite** — مناسب لمقياس البوت الحالي.
4. **Facade** (`core/mikrotik_api.py`) — واجهة موحّدة نظيفة تخفي `librouteros`.
5. **Error Classification** (`utils/error_response.py`) — رسائل عربية موجّهة للمستخدم.

---

## 14. الأولويات النهائية (Final Priorities)

| التحسين | الفائدة | تكلفة التنفيذ | الأولوية | الدليل |
|---|---|---|---|---|
| تقليل `ThreadPoolExecutor` workers (50→10-15) | يمنع استنزاف الخيوط تحت الحمل | Low | **High** | `async_blocking.py:18` |
| تثبيت `pyright` + strict في CI | يمنع أخطاء typing قبل الدمج | Low | **High** | `pyrightconfig.json` (معطّل حالياً) |
| تطبيق Navigation Guard على كل handlers | يمنع عمليات بلا راوتر | Medium | Medium | `handler_registry.py:224-226` |
| Pagination على مستوى API (`list_users`/`search`) | يقلل استهلاك الذاكرة للقوائم الكبيرة | Medium | Medium | `userman_manager.py:320-334` |
| إزالة `database/models.py` shim | يقلل coupling غير مبرر | Medium | Medium | `database/models.py` |
| استخراج duplicate code في `reboot.py` | يسّهل الصيانة | Low | Low | `reboot.py:69-84` |
| Graceful shutdown صريح في `main.py` | إغلاق نظيف للاتصالات | Low | Low | `mikrotik_api.close()` |

---

## 15. قواعد المراجعة المطبّقة + التقييم النهائي

- ✅ كل ملاحظة مدعومة بدليل `ملف:دالة:سطر` حقيقي.
- ✅ لا اقتراح patterns بلا مشكلة موثّقة.
- ✅ الكود الجيد ذُكر صراحةً (Connection Pool, Repository, Security, Error Classification).
- ✅ الفرق بين "مشكلة حالية" و"تحسين مستقبلي" واضح في كل قسم.

### نقاط القوة
1. Connection Pool ذكي (طوابير per-router + retry + كاش TTL).
2. Error Classification موجّه للمستخدم (رسائل عربية واضحة).
3. Registry Pattern مركزي يضمن ترتيب تسجيل صحيح.
4. تشفير كلمات المرور (Fernet) وإخفاء الأسرار في السجلات.
5. Navigation Guard تلقائي على operational handlers.
6. اختبار `tests/test_registration_order.py` يحمي من أخطاء precedence.

### نقاط الضعف
1. `ThreadPoolExecutor(max_workers=50)` — كبير جداً لعمليات MikroTik.
2. `pyright` غير مثبت رغم وجود الإعدادات.
3. Pagination غير مطبّق على مستوى API.
4. Navigation Guard غير متسق التغطية.
5. دوال طويلة في `userman.py`.

### المخاطر المصنّفة
| الخطر | الاحتمالية | التأثير |
|---|---|---|
| SQLite busy تحت حمل عالي | Medium | High |
| ThreadPool exhaustion | Medium | Medium |
| callback_data > 64 بايت | Low | Medium |
| pyright غائب | High | Low |

### الديون التقنية
1. `database/models.py` shim (إزالة تدريجية)
2. دوال طويلة في `userman.py`/`create_cards`
3. ThreadPool sizing
4. pyright غير مثبت

### خطة التحسين (High ROI)
1. تقليل ThreadPool workers — تكلفة Low، فائدة High.
2. تثبيت pyright — تكلفة Low، فائدة High.
3. تغطية Navigation Guard الكاملة — تكلفة Medium، فائدة Medium.
4. Pagination على مستوى API — تكلفة Medium، فائدة Medium.

---

## التقييم النهائي: **B+**

**المبرّر:** المشروع بُني بمعمارية صلبة — فصل طبقات جيد، واجهة API موحّدة، وآليات أمان وأخطاء قوية. النواقص (50 خيطاً، pyright غائب، pagination ناقص، تغطية nav guard جزئية) **ليست كارثية** لكنها تؤثر على الاستقرار تحت الحمل والصيانة طويلة المدى. الدرجة B+ تعكس "جيد جداً مع فرص تحسين واضحة ومحدودة وقابلة للتنفيذ بثقة عالية".
