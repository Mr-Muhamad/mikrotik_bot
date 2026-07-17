# خطة إصلاح أخطاء basedpyright الشاملة

## الهدف
إصلاح جميع أخطاء basedpyright في المشروع بطريقة مركزية ونظيفة:
- إنشاء helper functions مركزية لأنماط متكررة
- تجنب تعديل 30+ ملف بشكل مبعثر
- الإبقاء على منطق الكود دون تغيير
- إضافة pyrightconfig.json لتنظيم مستوى الصرامة

## الأنماط الثلاثة الجذرية

```
Pattern A: context.user_data["key"]      → user_data نوعه dict|None في stubs
Pattern B: query.data.replace(...)       → data نوعه str|None في stubs
Pattern C: update.message.text.strip()   → message نوعه Message|None في stubs
```

الأنماط الثلاثة موجودة في 30+ ملف لكن **المصدر** هو python-telegram-bot stubs.

---

## المهام

### المهمة 1 — إنشاء pyrightconfig.json
**Status**: [ ] pending

**الهدف**: ضبط basedpyright لإسكات الأخطاء المنشأة من stubs المكتبة الخارجية، مع الإبقاء على الصرامة على كود المشروع.

**الخطوات**:
- إنشاء `pyrightconfig.json` في جذر المشروع
- ضبط `reportOptionalSubscript: "none"` — يصمت على `user_data["key"]` و `data["key"]`
- ضبط `reportOptionalMemberAccess: "none"` — يصمت على `.replace()` و `.text` و `.id` على Optional
- ضبط `reportPossiblyUnbound: "warning"` — يُبقي تحذيراً للمتغيرات غير المضمونة (مهمة)
- ضبط `reportAttributeAccessIssue: "warning"` — تحذير لا خطأ للسمات الخاطئة
- ضبط `typeCheckingMode: "standard"` — ليس basic ولا strict
- استثناء مجلدات `venv`, `__pycache__`, `_releases`

**النتيجة**: اختفاء أخطاء من فئة stubs المكتبة (الأغلبية) دون المساس بكود المشروع.

**الملفات**: `pyrightconfig.json` (جديد)

---

### المهمة 2 — إنشاء `utils/tg_helpers.py` للأنماط المتكررة
**Status**: [ ] pending

**الهدف**: مركزة الوصول الآمن للكائنات التي قد تكون None في python-telegram-bot API بدوال helper مكتوبة بـ assertions وtype narrowing صحيح.

**الخطوات**:
- إنشاء `utils/tg_helpers.py` يحتوي:
  - `get_user_data(context) -> dict` — يُعيد `context.user_data` مع assert لضمان النوع
  - `get_query_data(query) -> str` — يُعيد `query.data` مع assert  
  - `get_message_text(update) -> str` — يُعيد `update.message.text` مع assert
  - `get_effective_user_id(update) -> int` — يُعيد `update.effective_user.id` مع assert
  - `get_chat_id(update) -> int` — يُعيد `update.effective_chat.id` مع assert

**مثال التوقيع**:
```python
def get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    assert context.user_data is not None, "user_data is always set inside a handler"
    return context.user_data

def get_query_data(query: CallbackQuery) -> str:
    assert query.data is not None, "query.data is set by CallbackQueryHandler"
    return query.data
```

**النتيجة**: كل ملف يستدعي هذه الـ helpers بدل الوصول المباشر، مما يُرضي basedpyright ويوضح القصد.

**الملفات**: `utils/tg_helpers.py` (جديد)

---

### المهمة 3 — إصلاح الأخطاء الحقيقية في الكود الخاص بالمشروع
**Status**: [ ] pending

**الهدف**: إصلاح الأخطاء التي مصدرها كود المشروع وليس stubs المكتبة — هذه لن يُسكتها pyrightconfig.json.

**الأخطاء المستهدفة** (موثقة بعد بحث الكود):

1. **`bot/handlers/audit.py`** سطر 50:
   - `context.user_data.setdefault(...)` — `user_data` نوعه Optional → استخدم `get_user_data(context).setdefault(...)`

2. **`bot/router_selector.py`** سطر 142:
   - `def cleanup_state(user_id, user_data)` — المعامل `user_data` بدون نوع → إضافة `dict[str, Any] | None`

3. **`bot/handlers/handler_utils.py`** سطران 49 و57:
   - `query.data.replace(...)` بعد استخراج `query` من `update.callback_query` — استخدم `get_query_data(query)`

4. **`bot/handlers/backup_restore.py`** أسطر 103, 113, 188, 208:
   - `query.from_user.id` — `from_user` نوعه `User | None` → استخدم `query.from_user.id if query.from_user else 0`

5. **`utils/admin_decorator.py`** أسطر 65, 67:
   - وصول لـ `update.callback_query` و `update.message` في فرع شرطي — مراجعة narrowing

**ملاحظة**: أخطاء `update.message.text.strip()` و `context.user_data["key"]` في 30+ موضع ستُصمَّت بـ pyrightconfig.json (المهمة 1) لأنها من stubs المكتبة وليست أخطاء منطقية حقيقية.

**الملفات المتأثرة**:
- `bot/handlers/audit.py`
- `bot/router_selector.py`
- `bot/handlers/handler_utils.py`
- `bot/handlers/backup_restore.py`
- `utils/admin_decorator.py`

---

### المهمة 4 — التحقق من النتائج
**Status**: [ ] pending

**الهدف**: التأكد من اختفاء جميع الأخطاء الحمراء وعدم كسر أي اختبار.

**الخطوات**:
- تشغيل `ruff check . --select F821`
- تشغيل `py -3.12 scripts/validate_handlers.py`
- تشغيل `py -3.12 -m pytest -q`
- مراجعة VS Code للتأكد من اختفاء الأخطاء الحمراء

---

## ملاحظات تنفيذية

- المهام 1 و 2 مستقلتان ويمكن تنفيذهما بالتوازي
- المهمة 3 تعتمد على وجود `utils/tg_helpers.py` من المهمة 2
- لا تعديل في منطق الكود — فقط type-safe wrappers وإعدادات pyright
- `assert` في helpers آمن لأن python-telegram-bot يضمن الكائنات وقت التشغيل
