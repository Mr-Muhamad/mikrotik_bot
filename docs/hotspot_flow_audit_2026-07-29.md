# تدقيق شامل لتدفقات إدارة Hotspot

**التاريخ:** 2026-07-29  
**الدقة:** عالية (تم قراءة كل سطر من الكود ومقارنته بـ AGENTS.md)  
**النطاق:** `/add`, `/edit`, `/delete`, `/search`, `/cards`, `/report`, `/usage`

---

## ملخص النتائج

| الخطورة | العدد | الوصف |
|---------|-------|-------|
| 🔴 **حرج** | 2 | أعطال منطقية تسبب سلوك خاطئ أو crashes |
| 🟠 **عالي** | 5 | انحرافات عن مواصفات AGENTS.md |
| 🟡 **متوسط** | 1 | مشاكل جودة كود (بنية الخطأ) |
| 🟢 **منخفض** | 0 | — |

---

## 🔴 مشاكل حرجة (High Confidence)

### 1. `/delete` — حذف المستخدم بدون `active-remove` (طرد الجلسات النشطة)

**الملف:** `bot/handlers/hotspot_delete.py`  
**السطر:** 148  
**الوصف:** عند تأكيد حذف مستخدم، يتم فقط استدعاء `hotspot_manager.delete_user()` الذي ينفذ `ip/hotspot/user/remove`. AGENTS.md ينص صراحةً على أن الحذف يجب أن يعمل أيضاً `active-remove` للطرد (`ip/hotspot/active/remove`).

**النص في AGENTS.md:**
> عند التأكيد يحذف من الراوتر ويعمل `active-remove` للطرد

**الكود الحالي (سطر 148):**
```python
await run_blocking(hotspot_manager.delete_user, router_key, user_id)
```

**المشكلة:** المستخدم الذي لديه جلسات نشطة يبقى متصلاً بالراوتر حتى بعد حذفه من قائمة المستخدمين. هذا يعني أن الحذف غير مكتمل ولا يطرد المستخدم فعلياً.

**الإصلاح المقترح:**
```python
# حذف المستخدم من قائمة المستخدمين
await run_blocking(hotspot_manager.delete_user, router_key, user_id)
# طرد أي جلسات نشطة
username = context.user_data.get("delete_username", "")
if username:
    await run_blocking(hotspot_manager.kick_user, router_key, username)
```

**ملاحظة:** يجب تخزين اسم المستخدم (`username`) في `context.user_data` أثناء خطوة `hotspot_delete_select` (سطر 87) حتى يتوفر في `confirm_callback`.

**الملف المتأثر:** `core/hotspot_manager.py` — `delete_user()` (سطر 205-210) لا يفعل سوى `ip/hotspot/user/remove` بدون أي `active-remove`.

---

### 2. `/report` — استخدام `context.user_data["router_key"]` مباشرة (خطر KeyError)

**الملف:** `bot/handlers/hotspot_report.py`  
**السطر:** 81  
**الوصف:** الأمر `/report` يستخدم الوصول المباشر لقاموس `context.user_data["router_key"]` بدلاً من استخدام `get_selected_router()` مع قيمة افتراضية احتياطية. إذا لم يكن `router_key` موجوداً في `user_data`، سيرفع الأمر `KeyError` ويحدث crash.

**الكود الحالي:**
```python
router_key = context.user_data["router_key"]  # سطر 81 — KeyError إذا لم يكن موجوداً
```

**المقارنة مع handlers الأخرى (الصحيحة):**
- `hotspot_add.py:113`: `router_key = get_selected_router(update.effective_user.id)` ✅
- `hotspot_delete.py:79`: `router_key = get_selected_router(query.from_user.id)` ✅
- `hotspot.py:95-97`: `router_key = get_selected_router(...)` مع fallback ✅
- `usage.py:62-64`: `router_key = get_selected_router(...)` مع fallback ✅

**الإصلاح المقترح:**
```python
router_key = get_selected_router(update.effective_user.id)
if not router_key:
    router_key = context.user_data.get("router_key")
if not router_key:
    await send_error(update, context, "لم يتم اختيار راوتر", log_extra="report_no_router")
    return
```

---

## 🟠 مشاكل عالية (High Confidence — انحرافات عن AGENTS.md)

### 3. `/add` — يُعيد `ConversationHandler.END` بدلاً من `WAITING_USERNAME` على النجاح

**الملف:** `bot/handlers/hotspot_add.py`  
**الأسطر:** 307 و 556  
**الوصف:** AGENTS.md ينص صراحةً على أن `/add` يجب أن يُعيد `WAITING_USERNAME` عند النجاح لتمكين الإضافة المتتالية دون إعادة تشغيل الأمر. الكود الحالي يُعيد `ConversationHandler.END` في كلتا الحالتين (التأكيد النصي والـ skip comment).

**النص في AGENTS.md:**
> يُعيد `WAITING_USERNAME` لتمكين الإضافة المتتالية

**الكود الحالي (سطر 307):**
```python
cleanup_state(update.effective_user.id, context.user_data)
return ConversationHandler.END  # ❌ يجب أن يكون WAITING_USERNAME
```

**الكود الحالي (سطر 556):**
```python
cleanup_state(query.from_user.id, context.user_data)
return ConversationHandler.END  # ❌ يجب أن يكون WAITING_USERNAME
```

**الإصلاح المقترح:** إعادة `WAITING_USERNAME` بدلاً من `ConversationHandler.END` عند النجاح، مع عرض رسالة نجاح تتضمن اسم المستخدم والبروفايل.

---

### 4. `/add` — رسالة النجاح لا تتضمن اسم المستخدم والبروفايل

**الملف:** `bot/messages.py`  
**السطر:** 73  
**الوصف:** `SUCCESS_ADD = "✅ تم إضافة المستخدم بنجاح"` لا يتضمن اسم المستخدم أو البروفايل. AGENTS.md ينص على أن رسالة التأكيد يجب أن تعرض "بالاسم والبروفايل".

**النص في AGENTS.md:**
> يعرض رسالة تأكيد بالاسم والبروفايل

**الكود الحالي:**
```python
SUCCESS_ADD = "✅ تم إضافة المستخدم بنجاح"
```

**الإصلاح المقترح:** تغيير الرسالة لتشمل اسم المستخدم والبروفايل، أو تمريرهما dynamically من الـ session:
```python
# في hotspot_add.py سطر 294
msg = SUCCESS_ADD.format(username=session.username, profile=session.profile)
await reply_final(update, context, msg, get_hotspot_keyboard())
```

---

### 5. `/report` — يعرض تقرير استخدام (bytes) بدلاً من إحصائيات شاملة

**الملف:** `bot/handlers/hotspot_report.py`  
**السطر:** 83  
**الوصف:** `/report` يستدعي `build_usage_report()` الذي يعرض تقرير استهلاك البيانات لكل مستخدم (top consumers, near-limit, expired). AGENTS.md ينص على أن `/report` يجب أن يعرض "إحصائيات شاملة (إجمالي/نشط/غير نشط/حسب البروفايل)".

**النص في AGENTS.md:**
> يعرض إحصائيات شاملة (إجمالي/نشط/غير نشط/حسب البروفايل) + تصدير CSV + تصدير Excel

**ما يعرضه `/report` فعلياً:**
- إجمالي المستخدمين، نشط، معطل، بحد بيانات
- الأكثر استهلاكاً (Top 5)
- مقترب من الحد، منتهٍ، غير نشط
- **بدون** توزيع حسب البروفايل (profile categories)

**ما يجب أن يعرضه (حسب AGENTS.md):**
- إجمالي/نشط/غير نشط
- **حسب البروفايل** (توزيع المستخدمين على الباقات)
- CSV + Excel export

**ملاحظة:** الإحصائيات الشاملة (مع توزيع البروفايل) موجودة في `/stats` عبر `hotspot.py` الذي يستخدم `get_hotspot_stats()`. الحل إما:
1. تغيير `/report` لاستخدام `get_hotspot_stats()` بدلاً من `build_usage_report()`
2. أو دمج البيانتين في `/report`

---

### 6. `/cards` — دفعة الكروت تُحفظ بدون ملخص المبيعات

**الملف:** `bot/handlers/hotspot_cards.py`  
**الأسطر:** 464-473  
**الوصف:** `save_card_batch()` تُستدعى بدون `unit_price` (القيمة الافتراضية 0.0)، مما يعني أن `total_price` سيكون 0.0 دائماً. AGENTS.md ينص على أن الدفعة يجب أن تُحفظ "مع ملخص المبيعات".

**النص في AGENTS.md:**
> يحفظ الدفعة في DB مع ملخص المبيعات

**الكود الحالي:**
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
    # ❌ unit_price مفقود — الافتراضي 0.0
)
```

**الإصلاح المقترح:**
1. إضافة سؤال عن سعر الوحدة قبل إنشاء الكروت (أو استخدام سعر البروفايل من الراوتر)
2. تمرير `unit_price` إلى `save_card_batch()`
3. عرض ملخص المبيعات بعد الإنشاء (عدد الكروت، إجمالي السعر، حالة الدفع)

---

### 7. `unblock_mac_handler` يفتقر إلى `cleanup_state()`

**الملف:** `bot/handlers/hotspot_search.py`  
**السطر:** 488  
**الوصف:** بعد إلغاء حظر MAC، يُعيد `unblock_mac_handler` `ConversationHandler.END` بدون استدعاء `cleanup_state()`. هذا يسبب تسرب حالة (state leakage) في `context.user_data`.

**المقارنة:**
- `block_mac_handler` (سطر 454): `cleanup_state(query.from_user.id, context.user_data)` ✅
- `show_blocked_list` (سطر 528): `cleanup_state(query.from_user.id, context.user_data)` ✅
- `unblock_mac_handler` (سطر 488): **يفتقر إلى `cleanup_state`** ❌

**الإصلاح المقترح:** إضافة `cleanup_state(query.from_user.id, context.user_data)` قبل `return ConversationHandler.END` في `unblock_mac_handler`.

---

## 🟡 مشاكل متوسطة (High Confidence — جودة الكود)

### 8. `except Exception` عام بدون تعليق يوضح السبب

**الملف:** `bot/handlers/hotspot_edit.py`  
**الأسطر:** 130, 229, 290, 357, 386, 448, 512, 627  
**الملف:** `bot/handlers/hotspot_delete.py`  
**السطر:** 151  

**الوصف:** AGENTS.md ينص: "ممنوع `except Exception` عام إلا لو فعلاً مقصود كنقطة نهاية (catch-all) قبل الرد على المستخدم. في الحالة دي لازم يتحط `# noqa: BLE001` مع تعليق يوضح السبب."

الكود الحالي يستخدم `# noqa: BLE001` فقط بدون تعليق يوضح السبب. هذا يخالف القاعدة.

**مثال (سطر 130 في hotspot_edit.py):**
```python
except Exception as e:  # noqa: BLE001
    # ❌ missing reason comment, e.g.:
    # noqa: BLE001 — catch-all for unexpected API errors before replying to user
```

**الإصلاح المقترح:** إضافة تعليق يوضح السبب لكل `except Exception` عام.

---

## ✅ التدفقات التي تتوافق مع AGENTS.md

| التدفق | الحالة | ملاحظات |
|--------|--------|---------|
| `/edit` | ✅ متوافق | يدعم تعديل جميع الحقول + kick + reset-counters + toggle disable/enable |
| `/search` | ✅ متوافق | يدعم `user:`, `mac:`, `ip:`, `comment:` + طرد + حظر/فك حظر MAC + عرض المحظورين |
| `/usage` | ✅ متوافق | يعرض الحالة/الخادم/البروفايل/كلمة المرور المموّهة/الحد/الوقت/التعليق/البايتات + الأجهزة النشطة |

---

## ملخص الإصلاحات المطلوبة (مرتبة بالأولوية)

| الأولوية | المشكلة | الملف | السطر |
|----------|---------|-------|-------|
| 🔴 P0 | `/delete` missing `active-remove` (kick) | `hotspot_delete.py` | 148 |
| 🔴 P0 | `/report` KeyError risk (`context.user_data["router_key"]`) | `hotspot_report.py` | 81 |
| 🟠 P1 | `/add` returns `END` instead of `WAITING_USERNAME` | `hotspot_add.py` | 307, 556 |
| 🟠 P1 | `/add` success message missing username/profile | `messages.py` | 73 |
| 🟠 P1 | `/report` shows usage report, not comprehensive stats | `hotspot_report.py` | 83 |
| 🟠 P1 | `/cards` missing sales summary (`unit_price`) | `hotspot_cards.py` | 464-473 |
| 🟠 P1 | `unblock_mac_handler` missing `cleanup_state` | `hotspot_search.py` | 488 |
| 🟡 P2 | Bare `except Exception` missing reason comments | `hotspot_edit.py`, `hotspot_delete.py` | Multiple |

---

## ملاحظات إضافية

### الفرق بين `/report` و `/stats`
- `/stats` (hotspot.py) → يستخدم `get_hotspot_stats()` → إحصائيات شاملة مع توزيع البروفايل
- `/report` (hotspot_report.py) → يستخدم `build_usage_report()` → تقرير استهلاك البيانات

AGENTS.md يصف `/report` كإحصائيات شاملة، لكن التنفيذ الحالي يعرض تقرير استخدام. هذا يحتاج إلى قرار: هل `/report` يجب أن يعرض الإحصائيات الشاملة (مثل `/stats`) أم تقرير الاستخدام (كما هو حالياً)؟

### `save_card_batch` و `update_batch_payment`
دالة `save_card_batch` في `database/repositories/card_batches.py` تدعم `unit_price` و `total_price` و `payment_status` و `sale_price`. لكن لا يوجد أي مكان في واجهة المستخدم يسمح بتحديد سعر الوحدة أو حالة الدفع عند إنشاء الدفعة. هذا يعني أن نظام المبيعات للكروت غير مكتمل.

### `delete_user` vs `kick_user` في `hotspot_manager.py`
- `delete_user()` (سطر 205-210): ينفذ `ip/hotspot/user/remove` فقط
- `kick_user()` (سطر 271-278): ينفذ طرد الجلسات النشطة

هاتان الدالتان منفصلتان ولا يتم استدعاؤهما معاً في أي مكان حالياً. يجب أن يستدعي `/delete` كليهما.
