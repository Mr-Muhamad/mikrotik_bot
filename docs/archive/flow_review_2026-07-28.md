# تقرير مراجعة تدفقات الوظائف — 2026-07-28

## الملخص

تمت مراجعة 7 تدفقات وظائف Hotspot الرئيسية ومقارنتها بالسلوك المتوقع المُعرَّف في `AGENTS.md`. تم اكتشاف **3 مخالفات** و**ملاحظة تصميمية واحدة**.

---

## 1. `/add` — إضافة مستخدم Hotspot

### السلوك المتوقع (AGENTS.md)
> يتحقق من عدم تكرار الاسم → يجلب البروفايلات من الراوتر → يُنشئ المستخدم بالبيانات المدخلة → يعرض رسالة تأكيد بالاسم والبروفايل. **يُعيد `WAITING_USERNAME` لتمكين الإضافة المتتالية.**

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| التحقق من عدم تكرار الاسم | ✅ | `hotspot_add_username` يستدعي `user_exists()` |
| جلب البروفايلات | ✅ | `hotspot_add_password` يستدعي `fetch_and_cache_profiles()` |
| إنشاء المستخدم | ✅ | `execute_add_user()` → `hotspot_manager.add_user()` |
| رسالة تأكيد | ✅ | `SUCCESS_ADD` مع اسم المستخدم والبروفايل |
| **إعادة `WAITING_USERNAME` للإضافة المتتالية** | ❌ **مخالفة** | بعد النجاح يُعيد `ConversationHandler.END` (سطر 307) |

### التفاصيل

في `hotspot_add.py:306-307`:
```python
cleanup_state(update.effective_user.id, context.user_data)
return ConversationHandler.END
```

بعد إضافة مستخدم بنجاح، تنتهي المحادثة. المستخدم يحتاج إلى إعادة `/add` لإضافة مستخدم آخر. وفقاً لـ AGENTS.md، يجب أن يُعيد `WAITING_USERNAME` لتمكين الإضافة المتتالية دون الحاجة لبدء أمر جديد.

**الملاحظة:** عند اكتشاف مستخدم مكرر، يُعيد `WAITING_USERNAME` بشكل صحيح (سطر 302). المشكلة هي فقط في حالة النجاح.

---

## 2. `/edit` — تعديل مستخدم Hotspot

### السلوك المتوقع (AGENTS.md)
> يبحث عن المستخدم → يعرض قائمة الحقول القابلة للتعديل (الاسم/كلمة المرور/البروفايل/البايتات/الوقت/التعليق) → يُنفّذ التعديل على الراوتر → يعرض تأكيداً. يدعم kick وreset-counters وtoggle disable/enable.

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| البحث عن المستخدم | ✅ | `hotspot_edit_search` → `search_users_for_action` |
| عرض الحقول القابلة للتعديل | ✅ | `get_edit_field_keyboard()` يعرض: name, password, profile, bytes, uptime, comment, toggle_disabled |
| تعديل الاسم | ✅ | مع تحقق من التكرار |
| تعديل كلمة المرور | ✅ | مع تحقق من الصلاحية |
| تعديل البروفايل | ✅ | عبر `edit_profile_selected` |
| تعديل البايتات | ✅ | مع إعادة حساب |
| تعديل الوقت (uptime) | ✅ | عبر `limit-uptime` |
| تعديل التعليق | ✅ | عبر `comment` |
| دعم kick | ✅ | `hotspot_edit_kick` |
| دعم reset-counters | ✅ | `hotspot_edit_reset` |
| دعم toggle disable/enable | ✅ | `toggle_disabled` داخل `hotspot_edit_field` |

### النتيجة: ✅ **مطابق للمتوقع**

---

## 3. `/delete` — حذف مستخدم Hotspot

### السلوك المتوقع (AGENTS.md)
> يبحث عن المستخدم → يعرض تأكيداً بالبيانات → عند التأكيد **يحذف من الراوتر ويعمل `active-remove` للطرد**. يُعيد `ConversationHandler.END`.

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| البحث عن المستخدم | ✅ | `hotspot_delete_search` → `search_users_for_action` |
| عرض التأكيد بالبيانات | ✅ | `CONFIRM_DELETE.format(format_hotspot_user(user))` |
| حذف من الراوتر | ✅ | `hotspot_manager.delete_user()` → `ip/hotspot/user/remove` |
| **`active-remove` للطرد** | ❌ **مخالفة** | لا يتم طرد الجلسات النشطة |
| إعادة `ConversationHandler.END` | ✅ | |

### التفاصيل

في `hotspot_delete.py:148`:
```python
await run_blocking(hotspot_manager.delete_user, router_key, user_id)
```

`delete_user()` في `core/hotspot_manager.py:204-209` ينفذ فقط:
```python
self._api.execute(router_key, "ip/hotspot/user/remove", **{".id": user_id})
```

**لا يوجد** استدعاء لـ `kick_user()` أو `ip/hotspot/active/remove` لطرد الجلسات النشطة.

**التأثير:** إذا كان المستخدم لديه جلسات نشطة، فسيتم حذفه من قائمة المستخدمين لكن جلساته ستظل نشطة حتى تنتهي صلاحيتها تلقائياً. وفقاً لـ AGENTS.md، يجب أن يتم `active-remove` للطرد الفوري.

**الإصلاح المقترح:** بعد `delete_user`، استدعاء `hotspot_manager.kick_user(router_key, username)` لإزالة الجلسات النشطة.

---

## 4. `/search` — بحث hosts

### السلوك المتوقع (AGENTS.md)
> يدعم بحث `user:`, `mac:`, `ip:`, `comment:` → يعرض نتائج مُرتبة بترقيم → يسمح بعرض التفاصيل + طرد + حظر MAC + فك حظر + عرض المحظورين.

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| دعم `user:` | ✅ | `hotspot_search_query` سطر 113 |
| دعم `mac:` | ✅ | سطر 115 |
| دعم `ip:` | ✅ | سطر 119 |
| دعم `comment:` | ✅ | سطر 117 |
| نتائج مُرتبة بترقيم | ✅ | `_format_search_results_text` يعرض الترقيم |
| عرض التفاصيل | ✅ | `hotspot_show_host` |
| طرد | ✅ | `hotspot_host_action` |
| حظر MAC | ✅ | `block_mac_handler` |
| فك حظر MAC | ✅ | `unblock_mac_handler` |
| عرض المحظورين | ✅ | `show_blocked_list` |

### النتيجة: ✅ **مطابق للمتوقع**

---

## 5. `/cards` — إنشاء كروت Hotspot

### السلوك المتوقع (AGENTS.md)
> يحدد العدد (حد أقصى 500) / الطول / البادئة / النوع (مختلفة/متشابهة/بدون كلمة مرور) / البروفايل / مدة الصلاحية / حد البايتات → يولّد PDF ويُرسله → **يحفظ الدفعة في DB مع ملخص المبيعات**.

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| تحديد العدد (حد 500) | ✅ | `MAX_HOTSPOT_CARDS = 500` |
| تحديد الطول | ✅ | `hotspot_cards_length` |
| تحديد البادئة | ✅ | `hotspot_cards_prefix` |
| تحديد النوع | ✅ | `hs_card_type1/2/3` |
| تحديد البروفايل | ✅ | `hotspot_cards_profile_selected` |
| تحديد مدة الصلاحية | ✅ | `hotspot_cards_uptime_type/value` |
| تحديد حد البايتات | ✅ | `hotspot_cards_bytes` |
| توليد PDF وإرساله | ✅ | `card_generator.generate_pdf()` + `send_document` |
| **حفظ الدفعة في DB مع ملخص المبيعات** | ⚠️ **ملاحظة** | يُحفظ في DB لكن بدون ملخص مبيعات |

### التفاصيل

في `hotspot_cards.py:464-475`:
```python
await run_blocking(
    save_card_batch,
    router_key=router_key,
    name=batch_name,
    batch_type="hotspot",
    profile=profile,
    comment_prefix=prefix,
    cards=serialize_cards(cards),
    created_by=update.effective_user.id if update.effective_user else None,
)
```

`save_card_batch()` (في `database/repositories/card_batches.py`) تقبل معامل `unit_price` (افتراضي `0.0`) وتحسب `total_price = round(count * unit_price, 2)`. لكن `hotspot_cards.py` لا يمرر `unit_price` أبداً، لذا السعر الإجمالي يكون دائماً 0.0.

**لا يوجد** "ملخص مبيعات" (sales summary) يُحفظ مع الدفعة. AGENTS.md ينص على أن الدفعة يجب أن تُحفظ "مع ملخص المبيعات".

**الملاحظة:** هذا قد يكون مقصوداً إذا كانت المبيعات تُتتبع بشكل منفصل، لكن AGENTS.md يذكر صراحةً "ملخص المبيعات" كجزء من حفظ الدفعة.

---

## 6. `/report` — تقرير Hotspot

### السلوك المتوقع (AGENTS.md)
> يعرض **إحصائيات شاملة** (إجمالي/نشط/غير نشط/حسب البروفايل) + تصدير CSV + تصدير Excel.

### الحالة الفعلية

| الخطوة | الحالة | الملاحظات |
|--------|--------|-----------|
| عرض إحصائيات شاملة (إجمالي/نشط/غير نشط/حسب البروفايل) | ❌ **مخالفة** | يعرض تقرير استخدام (bytes usage) وليس إحصائيات شاملة |
| تصدير CSV | ✅ | `report_export_csv` |
| تصدير Excel | ✅ | `report_export_excel` |

### التفاصيل

`report_command` في `hotspot_report.py:83`:
```python
report = await run_blocking(hotspot_manager.build_usage_report, router_key)
```

`build_usage_report()` في `core/hotspot_stats.py:170-268` يُنتج تقرير استخدام يركز على:
- استهلاك البايتات لكل مستخدم
- المستهلكين الأعلى
- المستخدمين المنتهين
- المستخدمين قريبين من الحد

**لا يحتوي** على:
- إجمالي المستخدمين
- عدد النشطين/غير النشطين
- توزيع حسب البروفايل

الإحصائيات الشاملة (إجمالي/نشط/غير نشط/حسب البروفايل) موجودة في `/stats` command (`hotspot.py:hotspot_stats`) عبر `get_hotspot_stats()`، وليس في `/report`.

**الإصلاح المقترح:** إما:
1. تغيير `/report` لاستخدام `get_hotspot_stats()` بدلاً من `build_usage_report()`، أو
2. تحديث `AGENTS.md` ليصف `/report` كتقرير استخدام (usage report) بدلاً من إحصائيات شاملة، مع الإشارة إلى أن الإحصائيات الشاملة متاحة عبر `/stats`.

---

## 7. `/usage` — تقرير استخدام مستخدم

### السلوك المتوقع (AGENTS.md)
> يبحث عن المستخدم → يعرض: الحالة/الخادم/البروفايل/كلمة المرور (مموّهة)/الحد/الوقت/التعليق/بايتات inbound+outbound+إجمالي + الأجهزة النشطة حالياً.

### الحالة الفعلية

| الحقل | الحالة | الملاحظات |
|-------|--------|-----------|
| الحالة | ✅ | `USAGE_STATUS_ACTIVE/DISABLED` |
| الخادم | ✅ | `USAGE_SERVER` |
| البروفايل | ✅ | `USAGE_PROFILE_LABEL` |
| كلمة المرور (مموّهة) | ✅ | `MASKED_PASSWORD = "********"` |
| الحد | ✅ | `USAGE_LIMIT_LABEL` |
| الوقت | ✅ | `USAGE_UPTIME_LABEL` |
| التعليق | ✅ | `USAGE_COMMENT_LABEL` |
| البايتات inbound | ✅ | `USAGE_BYTES_IN` |
| البايتات outbound | ✅ | `USAGE_BYTES_OUT` |
| الإجمالي | ✅ | `USAGE_BYTES_TOTAL` |
| الأجهزة النشطة | ✅ | `USAGE_CURRENT_ACTIVE` |

### النتيجة: ✅ **مطابق للمتوقع**

---

## ملخص المخالفات والملاحظات

| # | التدفق | المخالفة | الشدة | الإصلاح المقترح |
|---|--------|----------|-------|-----------------|
| 1 | `/add` | يُعيد `ConversationHandler.END` بدلاً من `WAITING_USERNAME` بعد النجاح | متوسط | تغيير `return ConversationHandler.END` إلى `return WAITING_USERNAME` في `hotspot_add_comment` و `skip_comment` |
| 2 | `/delete` | لا ينفذ `active-remove` لطرد الجلسات النشطة | **عالي** | إضافة استدعاء `hotspot_manager.kick_user(router_key, username)` بعد `delete_user` في `confirm_callback` |
| 3 | `/report` | يعرض تقرير استخدام بدلاً من إحصائيات شاملة | متوسط | إما تغيير `/report` لاستخدام `get_hotspot_stats()` أو تحديث `AGENTS.md` |
| 4 | `/cards` | لا يحفظ ملخص مبيعات مع الدفعة | منخفض | إضافة `unit_price` وملخص المبيعات إلى `save_card_batch` أو تحديث `AGENTS.md` |

---

## ملاحظة تصميمية

تدفق `/edit` يستخدم `_reply_or_edit()` helper (سطر 33-46 في `hotspot.py`) الذي يُرسل `parse_mode="HTML"` دائماً. هذا صحيح لعرض الرسائل بتنسيق HTML، لكنه يعني أن المعالجات لا يمكنها تغيير نوع التنسيق. هذا تصميم مقصود وليس مشكلة.

---

*التقرير أُعد في 2026-07-28 بواسطة Kilo*
