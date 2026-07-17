# خطة الإصلاح الشاملة لتوحيد تدفق بحث User Manager

## السياق
آخر 5 تعديلات وحدت البحث وإدارة المستخدمين (Hotspot + User Manager) في
تدفق مشترك. التحليل كشف عن خطأ تشغيلي حرج + عدة تناقضات بين تدفق
Hotspot (المرجع الصحيح) وتدفق User Manager. الهدف: إصلاح الخطأ + توحيد
سلوك التدفقين + تغطية الاختبارات.

---

## 1. إصلاح الخطأ الحرج — `userman_search.py:174`
`SEARCH_PROMPT` غير معرّف في هذا الملف (يُستورد `USERMAN_SEARCH_PROMPT` فقط).
يسبب `NameError` عند الضغط على "رجوع" في بحث User Manager بدون نتائج مخزنة.

**الإجراء:** في `userman_search_back` (السطر 174) استبدال:
```python
await edit_clean(query, context, SEARCH_PROMPT, get_cancel_keyboard())
```
بـ:
```python
await edit_clean(query, context, USERMAN_SEARCH_PROMPT, get_cancel_keyboard())
```
(`USERMAN_SEARCH_PROMPT` مُستورد أصلاً في السطر 12، ويُستخدم صحيحاً في 59 و61).

---

## 2. توحيد اختيار الراوتر — `userman_search.py:119`
`userman_search_action` يقرأ `context.user_data.get("router_key")` الذي **لا يضعه**
`userman_search_start` (عكس تدفق Hotspot الذي يقرأ `get_selected_router` مباشرة في
الاستعلام والإجراء). عند غياب المفتاح يخرج `userman_search_action` صامتاً
(`return ConversationHandler.END`) دون تنفيذ أي عملية.

**الإجراء:** في `userman_search_action` استبدال:
```python
router_key = context.user_data.get("router_key")
if idx is None or not hosts or not router_key:
    return ConversationHandler.END
```
بـ:
```python
router_key = get_selected_router(update.effective_user.id)
if idx is None or not hosts or not router_key:
    return ConversationHandler.END
```
(`get_selected_router` مُستورد أصلاً في السطر 18).

---

## 3. حارس التكرار للعمليات الخطرة — `userman_search.py`
سياسة `CLAUDE.md` تلزم `is_duplicate_callback()` على أزرار reboot/backup/delete.
تدفق User Manager يتعامل مع `um_delete` و`um_kick_execute` بدون حارس، ما يسمح
بحذف/طرد مزدوج عند الضغط المزدوج.

**الإجراء:** إضافة الاستيراد في السطر 22:
```python
from utils.callback_utils import safe_answer_callback, is_duplicate_callback
```
وفي بداية `userman_search_action` (بعد `await safe_answer_callback(query)`):
```python
if is_duplicate_callback(query.data, update.effective_user.id):
    return
```
يطابق النمط في `backup.py:42`, `hotspot_delete.py:78`, `reboot.py:52`.

---

## 4. تسجيل مفاتيح المحادثة — `bot/router_selector.py:19-34`
`search_um_hosts` و`kick_um_idx` (User Manager) غير معرّفة في
`CONVERSATION_USER_DATA_KEYS` بينما نظيراتها `search_hosts`/`kick_host_idx`
(Hotspot) معرّفة. هذا يخلق تداخلاً محتملاً لبيانات مخزنة بين التدفقات.

**الإجراء:** إضافة `"search_um_hosts", "kick_um_idx"` إلى tuple
`CONVERSATION_USER_DATA_KEYS` (بجوار `"search_hosts", "kick_host_idx"`).

---

## 5. إزالة التكرار — `hotspot_search.py:66-70`
السطران `text = ...` و`loading = ...` مكرران (لصق متبقٍ).

**الإجراء:** حذف الأسطر 69-70 المكررة، تارك الأسطر 66-67 فقط.

---

## 6. تنظيف الملفات المؤقتة والمراجع
- **حذف** `bot/handlers/states.py.e7843a99b7982e72cf3c11fc301d9d0d.tmp`
  (نسخة محرر قديمة من `states.py`، غير مُستوردة في أي مكان).
- **إعادة توجيه المراجع** إلى `CLAUDE.md` بدل `AGENTS.md` المحذوف:
  - `core/backup/system.py:15` و`:27` (تعليقات)
  - `docs/post-plan-best-practices.md:115`، `docs/priority-plan.md:25`،
    `docs/reconciliation-plan-vs-report.md:12,98`،
    `_releases/v1.1-quality/MANIFEST.md:20`، `MIGRATION_NOTES.md:217`
  - بديل: استعادة `AGENTS.md`. (الأفضل: تحديث المراجع لتفادي ملف مكرر.)
- `fix1.py` المحذوف: يُترك محذوفاً (سكريبت رملي مقصود حذفه).

---

## 7. تغطية الاختبارات — ملف جديد `tests/bot/handlers/test_userman_search.py`
لا يوجد أي اختبار لـ `userman_search.py`، وهذا سبب مرور `SEARCH_PROMPT` دون اكتشاف.

**الاختبارات المطلوبة** (بأسلوب الاختبارات القائمة في `test_hotspot_search.py`):
- `userman_search_start` يضبط `WAITING_USERMAN_SEARCH` وينظف الحالة.
- `userman_search_query` يعيد نتائج عند راوتر مختار، و`NO_ROUTER_SELECTED` عند غيابه.
- `userman_search_select` يضبط `kick_um_idx` ويتعامل مع فهرس غير صالح.
- `userman_search_action` (`um_kick_execute`/`um_reset_counters`/`um_toggle_disabled`/`um_delete`)
  يقرأ الراوتر عبر `get_selected_router` (موكّى) لا `user_data["router_key"]`.
- **اختبار يعيد إنتاج الخطأ**: `userman_search_back` مع `search_um_hosts=None`
  يجب ألا يرفع `NameError` (هذا يغطي الإصلاح 1).
- `is_duplicate_callback` يمنع التنفيذ المزدوج على `um_delete`.

---

## ترتيب التنفيذ
1. الإصلاح 1 (الخطأ الحرج) — أولوية قصوى.
2. الإصلاح 2 + 3 (توحيد الراوتر + الحارس) — يطابق سلوك Hotspot.
3. الإصلاح 4 + 5 (المفاتيح + إزالة التكرار).
4. الإصلاح 6 (تنظيف الملفات/المراجع).
5. الإصلاح 7 (الاختبارات).
6. **التحقق:** `python scripts/validate_handlers.py` + `ruff check . --select F821`
   + `pytest` (الهدف: 769→ يمر جميعها + اختبارات جديدة).

## المخاطر
- تغيير `userman_search_action` لقراءة `get_selected_router` قد يكشف راوتراً
  مختلفاً عما يفترضه `user_data` القديم — لكنه السلوك الصحيح والمطابق لـ Hotspot.
- حذف `.tmp` آمن (غير مُستورد). تحديث مراجع `AGENTS.md` نصي فقط.
