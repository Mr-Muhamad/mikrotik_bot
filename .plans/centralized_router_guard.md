# الخطة: حارس تنقّل ممركزي لفرض "راوتر نشط" قبل أي ميزة تشغيلية

## فهم المعمارية (التحليل لا التنفيذ)

### كيف يصل طلب المستخدم إلى المعالج
1. `main.py` → `build_all(application)` → `utils/handler_registry.build_application`.
2. كل معالج يُسجَّل عبر أحد المساعدات: `standalone()`، `entry_point()`،
   `state().callback()/.message()`، `fallback()`، أو `group().*` في
   `bot/registrations.py`.
3. عند البناء، كل قيد يمر عبر **نقطة الاختناق الوحيدة**:
   `utils/handler_registry._build_handler(entry)` (السطر 185) الذي يلفّ
   `entry["func"]` بـ `bind_request_id_from_update`. النتيجة تُمرَّر إلى
   `handler_cls(callback=wrapped, **kwargs)`.
4. المعالجات الملفوفة تُضاف إلى: CH منفصل (rename/manual_add) → CH رئيسي
   → standalone.

**النتيجة:** `_build_handler` هو المكان الوحيد الذي يمر عبره **كل** معالج
(standalone + entry + state + fallback + groups). أي تغليف هنا يُطبَّق تلقائياً
على الجميع دون تكرار داخل المعالجات الفردية.

### الحالة الحالية (المشكلة)
- `require_router` موجود فعلاً في `bot/router_selector.py:85`، لكنه يُطبَّق
  **يدوياً وبشكل غير منتظم**: فقط على جزء من نقاط الدخول (مثل
  `userman_cards_start`, `hotspot_add_start`, `backup_full`).
- نقاط دخول تشغيلية مهمة **بلا** الحارس: `hotspot_search_start`,
  `hotspot_edit_start`, `hotspot_delete_start`, `usage_start`, `report_command`,
  `logs_command`, `hotspot_menu`, `stats_menu`, `backup_menu`, أغلب قوائم
  `menu_*`, وأزرار القوائم `hotspot_add/hotspot_edit/hotspot_delete/hotspot_cards/
  userman_cards/...`.
- هذا يعني أن المستخدم يمكنه فتح قائمة تشغيلية أو بدء تدفق دون راوتر نشط،
  فيقع الخطأ لاحقاً داخل المعالج (أو يمر دون حارس).

---

## 1. أين تُفرض القاعدة أول مرة؟ (Earliest point)
**عند نقطة البناء `_build_handler` في `utils/handler_registry.py`.**
- لماذا: هي نقطة العبور الإجبارية لكل معالج. فرض الفحص هنا يعني أنه لا
  يوجد أي مسار (أمر/ضغط زر/رسالة نصية داخل state) يمكنه تجاوز القاعدة.
- بديل مرفوض: تطبيق `@require_router` يدوياً على كل معالج = تكرار ونسيان
  (وهو سبب المشكلة الحالية).

## 2. تصميم الحارس الممركز الوحيد
نبني دالة تغليف مركزية `require_active_router_guard(func)` في
`utils/handler_registry.py` (أو في `bot/router_selector.py` كـ `navigation_guard`).
السلوك:
- تقرأ `update.effective_user.id` → `get_selected_router(user_id)`.
- إن وُجد راوتر نشط → تنفّذ `func` كما هي (لا تغيّر السلوك الحالي).
- إن لم يوجد → ترسل `NO_ROUTER_SELECTED` + `get_router_keyboard()`
  (عبر `update.callback_query.edit_message_text` أو `update.message.reply_text`)
  و**لا تنفّذ** `func` (ترجع `None`/تُنهي).

يُضاف هذا التغليف **داخل `_build_handler`** بعد `bind_request_id_from_update`،
بحيث يلفّ المعالج النهائي إذا كان المعالج "تشغيلياً".

## 3. وراثة القوائم التشغيلية تلقائياً
لكل معالج مُسجَّل، نعرف **تصنيفاً** عند التسجيل: `operational` (يحتاج راوتر)
أو `router_mgmt` (معفى). نصنّف آلياً من `kwargs` المتاحة وقت التسجيل:
- `entry_point(CommandHandler, command=...)` / `standalone(CommandHandler, command=...)` →
  الأمر يندرج تحت إما معفى (انظر القائمة أدناه) وإما تشغيلي.
- `CallbackQueryHandler` → نصنّف من `pattern` (مثلاً `PATTERNS["menu_hotspot"]`
  تشغيلي، `PATTERNS["select_router"]` معفى).

يُخزَّن التصنيف في قيد التسجيل (`entry["requires_router"] = True/False`)،
وتستخدمه `_build_handler` لتبديل التغليف.

**قائمة المعفاة (router management — تبقى متاحة دائماً):**
- الأوامر: `start`, `help`, `cancel`, `clean`, `sync`, `routers`, `addrouter`,
  `reboot`, `roles`, `role`, `watchdog`, `metrics`.
- الـ callbacks: `select_router`, `main_menu`, `saved_routers`, `saved_router`,
  `discover_routers`, `connect_router`, `delete_router`, `confirm_delete_router`,
  `refresh_routers`, `reboot_yes/no/router`, `rename_router`, `manual_add_router`
  وأزرار `manual_add_*`، `cancel_edit`, `go_back`، وأي callback يخص اختيار/
  إضافة/حذف/إعادة تسمية الراوتر نفسه.

**كل ما عدا ذلك = تشغيلي** ويُغلَّف تلقائياً: قوائم `menu_hotspot`,
`menu_userman`, `menu_stats`, `menu_backup`, `menu_pdf_settings`، وأزرار
`hotspot_add/edit/delete/search/cards`, `userman_cards/list/profiles/search`,
`hotspot_stats`, `stats_*`, `backup_full/userman`, `usage`, `report*`,
`logs*`, `batch*`, `pdf_options/*`، ونقاط الدخول والـ states التابعة لها.

> ملاحظة: القوائم الفرعية (`hotspot_menu`, `userman_menu`, ...) نفسها تشغيلية،
> لكنها تعرض اسم الراوتر الحالي؛ فرض الحارس عليها يعيد توجيه المستخدم ببساطة
> لشاشة اختيار الراوتر إن لم يختر — وهو السلوك المطلوب.

## 4. تجنّب التكرار داخل المعالجات
- نزيل `@require_router` اليدوي من المعالجات الفردية
  (`userman.py`, `stats.py`, `hotspot_add.py`, `hotspot.py`, `hotspot_cards.py`,
  `batch.py`, `backup.py`, `hotspot_report.py`) لأنه سيصبح مكرراً مع الحارس
  الممركز.
- `require_router` في `router_selector.py` يُبقى كدالة قابلة لإعادة الاستخدام
  (قد تستعملها قوائم `menu_*` الداخلية `_internal_*` إن لزم)، لكن لا يُطلب
  تطبيقه يدوياً على نقاط الدخول بعد الآن.
- المعالجات الفردية لا تتحقق من الراوتر نهائياً → لا تكرار.

## 5. بقاء شاشات إدارة الراوتر متاحة
لأن التصنيف يُعفي صراحةً كل أوامر/أزرار إدارة الراوتر (القائمة أعلاه)، فإن
`select_router`, `saved_routers`, `discover_routers`, `manual_add_*`,
`rename_router`, `connect_router`, `delete_router_*`, `reboot_*` تعمل دون حارس
وتُعرض حتى قبل اختيار راوتر — تماماً كما اليوم.

---

## آلية التطبيق (ملخص — للتنفيذ لاحقاً)
1. في `utils/handler_registry.py`:
   - إضافة `_classify(entry)` تحدد `requires_router` من `entry["kwargs"]`
     (command/pattern) مقابل قائمة معفاة مركزية `ROUTER_MGMT_ALLOW`.
   - في `_build_handler`: بعد بناء `wrapped`، إن `entry.get("requires_router")`
     غلّفه بـ `navigation_guard(wrapped)`.
   - `_register`/`entry_point`/`standalone`/`state`/`fallback`/`group.*` تمرّر
     التصنيف عبر `_build_handler` (يُحسب من kwargs تلقائياً، لا حاجة لتغيير
     `bot/registrations.py` تقريباً).
2. نقل منطق الإعفاء إلى ثابت واضح (مثلاً في `bot/router_selector.py` أو
   `utils/handler_registry.py`): `ROUTER_MGMT_PATTERNS` و`ROUTER_MGMT_COMMANDS`.
3. إزالة `@require_router` اليدوي من المعالجات الفردية لتفادي التكرار.
4. **لا تغيير** في `bot/registrations.py` إلا إن لزم تمرير علم صريح (غير مستحسن؛
   التصنيف التلقائي من kwargs أفضل).

## التحقق المتوقع
- `python scripts/validate_handlers.py` يبقى أخضر.
- اختبار وحدة: معالج تشغيلي (مثل `hotspot_menu`) يُستدعى بلا راوتر → يُرجع
  `NO_ROUTER_SELECTED` ولا ينفّذ المنطق. معالج `select_router` يُستدعى بلا
  راوتر → يُنفَّذ طبيعياً.
- `pytest` الكامل يبقى أخضر (783 حالياً + الجديد).
- فحص `ruff --select F821` أخضر.
