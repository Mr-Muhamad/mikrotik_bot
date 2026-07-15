# Project Instructions

MikroTik Telegram Bot — بوت إدارة عن بُعد لموجّهات MikroTik RouterOS عبر Telegram.

## Tech Stack
- Python 3.12، `python-telegram-bot>=21` (ConversationHandler + JobQueue)
- `librouteros>=3.3` لواجهة MikroTik API (المنفذ 8728 افتراضياً)
- SQLite عبر `sqlite3` مباشرة (لا ORM) في `database/models.py`
- تشفير `cryptography` (Fernet) لكلمات مرور الروترات
- `reportlab` + `qrcode[pil]` + `Pillow` + `arabic-reshaper` + `python-bidi` لتوليد كروت PDF
- اختبار: `pytest` + `pytest-asyncio` (`asyncio_mode="auto"` في `pyproject.toml`)
- جودة: `ruff`

## Code Style
- الدوال/المتغيرات/أسماء الملفات: snake_case بالإنجليزية.
- النصوص العربية المعروضة للمستخدم توضع في `bot/messages.py` فقط، لا داخل handlers.
- لا تعليقات أو أمثلة `TODO`/`...` قصيرة عند كتابة كود جديد — اكتب الكود كاملاً وقابلاً للتشغيل.
- معالجات Telegram: `async def handler(update, context)`، مزخرفة بـ `@admin_only` عند الحاجة، وتعيد `ConversationHandler.END` أو اسم state.
- العمليات المتزامنة/البطيئة تُغلَّف بـ `run_blocking` (من `utils/async_blocking.py`) لعدم حجب event loop.
- استخدم `send_error()` أو معالجة خطأ واضحة عند فشل عمليات MikroTik أو Telegram.
- طبقة `core/` تبقى مستقلة عن Telegram قدر الإمكان.

## Architecture
- نقطة الدخول `main.py`: `init_db()` → بناء Application (`concurrent_updates(False)`) → `build_all()` → `post_init()` (أوامر Telegram + استعادة جدول النسخ + تشغيل watchdog).
- تسجيل المعالجات مركزي في `bot/registrations.py` فوق نظام registry في `utils/handler_registry.py` (`entry_point`, `state`, `fallback`, `standalone`).
- `ConversationHandler` رئيسي واحد يدير ~28 حالة لكل الميزات + CH منفصل لـ rename + handlers مستقلة للتنقل.
- التدفق: `bot/handlers/*` → `core/*managers` → `core/mikrotik_api` → `core/connection_pool` → librouteros.
- حالة الراوتر المختار في SQLite (`user_sessions`)؛ بيانات المحادثة المؤقتة في `context.user_data`.

## Security
- `BOT_TOKEN`, `ADMIN_IDS`, `ENCRYPTION_KEY` إلزامية في `config.py` (يتوقف التشغيل إن غابت/كانت قصيرة).
- لا تعرض كلمات المرور في logs أو رسائل Telegram (`_debug_log` يخفيها، `decrypt_password` يعيد نصاً فارغاً عند الفشل).
- `update_pdf_settings()` يستخدم whitelist للأعمدة (`PDF_ALLOWED_COLUMNS`) — لا تبنِ SQL ديناميكياً خارج هذا النمط.
- استخدم `is_duplicate_callback()` في callbacks الخطرة (reboot/backup/delete).
- مفتاح الراوتر المحفوظ يأخذ الشكل `discovered_{db_id}`.

## Testing
- تشغيل: `pytest`
- فحص اتساق التسجيل (إلزامي بعد تعديل handlers): `python scripts/validate_handlers.py`
- فحص أسماء غير معرّفة: `ruff check . --select F821`
- التجميع: `tests/` مقسمة إلى `core/`, `bot/`, `utils/`, `database/`, `integration/`, مع `mocks/` و`fixtures/`.

## Build & Run
- التشغيل: `python main.py` (يتطلب `.env`)
- التبعيات: `pip install -r requirements.txt`
- لا تضف تسجيل معالجات مباشرة في `main.py`؛ المسار عبر `bot/registrations.py`.

## Adding a Command (تسجيل جديد)
1. أنشئ handler في `bot/handlers/` مع `@admin_only` عند الحاجة.
2. صدّره من `bot/handlers/__init__.py`.
 3. سجّله في `bot/registrations.py` (`standalone`/`entry_point`/`state`/`fallback`).
 4. أي `callback_data` جديد يُعرّف في `bot/handlers/callback_constants.py` (`CALLBACKS` أو أحد البناة) ويُضاف نمطه إلى `PATTERNS`، ثم يُستدعى من `bot/registrations.py` باسم النمط لا بنمط مضمّن.
 5. أضفه إلى `utils/bot_commands.py` لظهوره في قائمة Telegram السريعة.
 6. حدّث `HELP` في `bot/messages.py` إن كان موجّهاً للمستخدم.
 7. شغّل `python scripts/validate_handlers.py`.

## Conventions
- رتّب callback patterns من الأكثر تحديداً إلى الأعمع عند التعارض.
- كل start handler في تدفق جديد ينظّف الحالة عبر `cleanup_state()` ويضبط `nav_set()`.
- المفاتيح المؤقتة في `context.user_data` محددة في `CONVERSATION_USER_DATA_KEYS` (`bot/router_selector.py`).
- العمليات الثقيلة (backup/جلب قوائم كبيرة) تستخدم `execute_long()`.
- أوامر MikroTik: `reset-counters` يستخدم `numbers=` لا `.id`؛ User Manager يختلف مساره بين v6 (`tool/user-manager`) وv7 (`user-manager`) عبر `get_userman_base_path()`.
- إعدادات logging حصراً في `main.py` قبل `configure_logging()`؛ لا تضف `logging.basicConfig` جديداً.

## RouterOS Compatibility Policy

- The project officially supports both RouterOS v6 and RouterOS v7.

- Any proposed implementation must preserve compatibility with both versions unless the user explicitly requests a v7-only feature.

Do not recommend RouterOS v7-specific APIs (such as REST API) or commands unless:
1. The target router is confirmed to be RouterOS v7.
2. The feature is explicitly marked as v7-only.
3. A compatible fallback for RouterOS v6 is provided when applicable.