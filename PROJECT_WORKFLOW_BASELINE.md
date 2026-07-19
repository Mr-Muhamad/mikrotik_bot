# MikroTik Telegram Bot - Workflow Baseline

## 1. مسار إضافة المعالجات (Handlers)
أي أمر جديد أو زر (Callback) يجب أن يُسجل في `bot/registrations.py` ويتم إنشاؤه في ملفه المخصص داخل `bot/handlers/`. لا يسمح بتسجيل المعالجات بشكل مباشر في `main.py`. 
يتم استخدام نمط `PATTERNS` و `CALLBACKS` من `bot/handlers/callback_constants.py` للمحافظة على توحيد الأسماء ومنع التعارض.

## 2. إدارة البيانات وحالة المحادثات (State Management)
يُمنع استخدام القواميس البدائية (مثل `context.user_data["add_username"]`) لتخزين البيانات المؤقتة. بدلاً من ذلك، تُستخدم نماذج الـ `Dataclasses` الموجودة في `session_models.py` (مثل `HotspotAddSession`). ويجب دوماً استخدام دالة `cleanup_state()` في نهاية أو إلغاء المحادثة لتنظيف الذاكرة.

## 3. رسائل المستخدم (User Messages)
للحفاظ على قابلية التوسع وسهولة الترجمة، كافة الرسائل النصية الموجهة للمستخدم يجب أن تُستدعى من `bot/messages.py` ولا يتم وضع نصوص حرفية (Hardcoded) داخل المعالجات.

## 4. الاعتماديات (Dependencies) 
أي إضافة لمكتبة جديدة يجب أن توثق في `requirements.txt` و `requirements-dev.txt` إن لزم الأمر. المخططات الجديدة في قواعد البيانات يجب أن تمر عبر `alembic revision` بدلاً من تنفيذ أوامر `CREATE TABLE` مباشرة في الكود.

## 5. قواعد الأمان والتوثيق (Security & Logging)
- تُسجل الأخطاء الحميدة (Benign Errors) لتيليجرام على مستوى `DEBUG` في `utils/error_response.py`.
- يتم تسجيل العمليات المهمة بـ `request_id` للتتبع.
- يمنع طباعة أي أرقام سرية (Passwords) أو حفظها في السجلات (Logs)، ويجب دائماً تمريرها عبر دوال التشفير (`encrypt_password`) من `utils/crypto.py`.
