# تقرير مقارنة مشروع MikroTik Telegram Bot

تاريخ التقرير: 2026-07-09

## 1. الملخص التنفيذي

المشروع في حالته الحالية قريب من التوثيق المحلي بدرجة جيدة، ويظهر أنه بُني كمنظومة تشغيلية فعلية لا كنموذج أولي. التسجيل مركزي، تدفقات Telegram منظمة حول `ConversationHandler`، كلمات مرور الراوترات مشفرة محلياً، وهناك اختبارات واسعة تغطي وحدات وتدفقات كثيرة.

المعياران المطلوبان في هذا التقييم هما:

- دعم RouterOS v6 وRouterOS v7.
- عدم افتراض وجود شهادة SSL على الراوتر، وبالتالي الاعتماد العملي على RouterOS API العادي عبر المنفذ `8728`.

بناءً على ذلك، الاتصال الحالي عبر `librouteros` و`DEFAULT_API_PORT = 8728` مناسب كمسار افتراضي متوافق مع v6/v7. لا ينبغي اقتراح REST/HTTPS كبديل أساسي لأنه لا يغطي v6 جيداً، ولا يناسب قيد عدم وجود شهادة SSL. يمكن فقط اعتباره خياراً مستقبلياً لبعض راوترات v7 في بيئات منفصلة.

أهم فجوة ليست في قابلية التشغيل، بل في تخفيف مخاطر الاتصال غير المشفر، وتحويل بعض القدرات الموجودة إلى تجربة إدارية أقوى: لوحة حالة، تقارير استخدام، صلاحيات داخل البوت، تنبيهات ذكية، وسياسات احتفاظ أوضح للنسخ الاحتياطية والسجلات.

## 2. واقع الكود مقابل التوثيق

### نقاط مطابقة قوية

- `main.py` يطابق التوثيق في تهيئة قاعدة البيانات، بناء `Application`, استخدام `JobQueue`, استدعاء `post_init`, وتسجيل المعالجات عبر `build_all(application)` بدلاً من التسجيل اليدوي داخل `main.py`.
- `concurrent_updates(False)` مفعّل، وهذا يتوافق مع توثيق `python-telegram-bot` الذي يحذر من المعالجة المتزامنة مع `ConversationHandler` لأن المحادثات تعتمد على معالجة التحديثات بالتسلسل.
- `post_init()` يضبط أوامر Telegram، يستعيد جدولة النسخ الاحتياطي، ويبدأ watchdog إذا لم يكن موجوداً.
- `utils/registrations.py` هو مركز تسجيل الأوامر، callbacks، states، fallbacks، ومعالج الأخطاء.
- `utils/handler_registry.py` يلف المعالجات عبر `bind_request_id_from_update`، وهذا يحافظ على `request_id` في السجلات.
- `bot/handlers/routers.py` يعمل كواجهة توافق، والتنفيذ الفعلي موجود في `bot/handlers/router_flows/` كما يقول التوثيق.
- `core/backup_service.py` يعمل كواجهة توافق فوق `core/backup/`.
- `config.py` يوقف التشغيل عند غياب `BOT_TOKEN`, `ADMIN_IDS`, أو `ENCRYPTION_KEY`، ويتحقق من صلاحية مفتاح Fernet.
- `database/models.py` يستخدم SQLite مع WAL و`busy_timeout`، ويشفر كلمات مرور الراوترات عند الحفظ ويفكها فقط عند الحاجة.

### نقاط تحتاج ضبطاً أو توثيقاً أوضح

- التوثيق يحذر من رفع `mikrotik_bot.db`, `backups/`, و`logs/`. ملف `.gitignore` يحتوي قواعد مناسبة، لكن هذه الملفات موجودة فعلياً داخل مجلد العمل. بما أن المجلد الحالي لم يظهر كمستودع Git عند تشغيل `git status`، لا يمكن الجزم بأنها مرفوعة، لكنها تظل مخاطرة تشغيلية محلية.
- `venv` المحلي موجود لكنه يشير إلى Python غير موجود في المسار:
  `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`.
  لذلك تم استخدام `py -3.12` لتشغيل الفحوص.
- `README.md` يذكر تفعيل خدمة `api` على المنفذ `8728`، وهذا متوافق مع القيد المطلوب. لكن يجب أن يضيف توصيات تقييد خدمة API لأن الاتصال غير مشفر.
- توجد أوامر مستخدم ورسائل عربية كثيرة في `bot/messages.py`، لكن المميزات الإدارية المتقدمة مثل صلاحيات داخلية وتقارير قابلة للتصدير ليست ممثلة بعد كواجهات واضحة.

## 3. دعم RouterOS v6 وv7

### الموجود حالياً

- `core/mikrotik_api.py` يحتوي `get_userman_base_path()`:
  - v7 يستخدم `user-manager`.
  - v6 يستخدم `tool/user-manager`.
  - عند فشل معرفة الإصدار يرجع إلى مسار v6 كافتراض محافظ.
- `core/userman_manager.py`, `core/profile_sync.py`, `core/backup/userman.py`, و`core/stats.py` تستخدم `get_userman_base_path()` بدلاً من تثبيت مسار واحد.
- الاختبارات تغطي الحالتين v6/v7 في `tests/core/test_mikrotik_api.py`, `tests/core/test_profile_sync.py`, `tests/core/test_userman_manager.py`, و`tests/core/test_stats.py`.
- أوامر Hotspot الأساسية مثل `ip/hotspot/user/print`, `ip/hotspot/active/print`, و`ip/hotspot/host/print` مناسبة عموماً لكلا الإصدارين.

### المخاطر المتبقية

- User Manager أكثر منطقة معرضة لاختلافات v6/v7، خصوصاً أسماء الحقول المقبولة عند إنشاء profiles/users أو استعادتها من backup.
- `userman_restore()` يعيد إنشاء profiles/users اعتماداً على حقول محددة. هذا عملي، لكنه يحتاج اختبارات واقعية على راوتر v6 وv7 لأن RouterOS قد يرفض حقولاً موجودة في إصدار وغير موجودة في الآخر.
- `get_version()` يعتمد على `system/resource/print` ويخزن الإصدار في cache لمدة طويلة. هذا جيد للأداء، لكن بعد ترقية RouterOS قد يبقى المسار القديم مستخدماً حتى انتهاء الكاش أو إعادة التشغيل.

### التوصية

الحفاظ على `librouteros` كطبقة اتصال أساسية موحدة لكلا الإصدارين، وإضافة مصفوفة توافق داخلية موثقة للأوامر والحقول الحساسة:

- Hotspot users/active/hosts.
- User Manager users/profiles.
- backup/export/import.
- reset counters.
- restore fields.

لا حاجة لنقل الاتصال إلى HTTP/REST. الأفضل تقوية اختبارات التوافق وإضافة فحص version/capabilities عند حفظ الراوتر.

## 4. الاتصال بدون SSL

### التقييم

حسب توثيق MikroTik، RouterOS API يستخدم افتراضياً `TCP 8728`، وهناك منفذ آمن `8729`. وبما أن الراوترات لا تملك شهادة SSL، فإن الاعتماد على `8728` هو اختيار تشغيلي مقبول بشرط ألا يكون مكشوفاً خارج شبكة موثوقة.

الكود الحالي:

- يستخدم `DEFAULT_API_PORT = 8728`.
- يخزن منفذ كل راوتر في `discovered_routers.port`.
- يستخدم `librouteros.connect()` بدون TLS.
- لا يعرض كلمات المرور في رسائل المستخدم، ويخفي حقول password في debug logs داخل `_debug_log()`.

### مخاطر الاتصال غير المشفر

- اسم المستخدم وكلمة المرور وأوامر الإدارة تمر داخل الشبكة بدون تشفير RouterOS API.
- أي جهاز داخل نفس الشبكة الإدارية أو في مسار المرور قد يستطيع مراقبة الاتصال إذا كانت الشبكة غير معزولة.
- فتح `8728` على الإنترنت خطر عالٍ جداً، خصوصاً أن الراوترات هدف شائع للهجمات.

### ضوابط تخفيف لا تتطلب SSL

هذه الضوابط هي الأهم لأنها تحافظ على v6/v7 ولا تحتاج شهادة:

1. تقييد خدمة API في MikroTik إلى عنوان IP جهاز البوت فقط عبر `/ip service set api address=...`.
2. إنشاء مستخدم MikroTik خاص للبوت بصلاحيات أقل ما يمكن، وليس `admin` العام.
3. منع الوصول إلى `8728` من WAN نهائياً عبر firewall.
4. تشغيل البوت داخل شبكة إدارة منفصلة أو VLAN خاصة.
5. تعطيل خدمات MikroTik غير المستخدمة مثل `telnet`, `ftp`, أو `www` إذا لم تكن مطلوبة.
6. تفعيل سجلات فشل الاتصال داخل البوت وربطها بتنبيه Telegram للمشرف.
7. تدوير كلمة مرور مستخدم البوت دورياً، خصوصاً إذا انتقل جهاز البوت أو تغيرت الشبكة.
8. الاحتفاظ بـ `ENCRYPTION_KEY` خارج Git وخارج الرسائل والسجلات.

## 5. أفضل الممارسات المناسبة للمشروع

### Telegram bot architecture

- الإبقاء على `concurrent_updates(False)` مع `ConversationHandler`.
- إبقاء التسجيل في `utils/registrations.py` وعدم إضافة handlers مباشرة في `main.py`.
- استخدام `run_blocking()` لأي عملية MikroTik أو ملفية قد تحجب event loop.
- الاستمرار في استخدام `safe_answer_callback()` و`is_duplicate_callback()` للعمليات الخطرة مثل reboot, backup, restore, delete.
- إضافة timeouts ورسائل فشل واضحة في كل flow طويل حتى لا يظل المستخدم بلا نتيجة.

### Security

- لا يتم فرض API-SSL بسبب القيد المطلوب، لكن يجب توثيق `8728` كاتصال غير مشفر يحتاج عزل شبكة.
- فصل صلاحيات Telegram إلى أدوار داخلية بدلاً من الاعتماد فقط على `ADMIN_IDS`.
- عدم تسجيل responses الخام من MikroTik إلا بعد `sanitize_api_response()`.
- إضافة فحص إعدادات startup يحذر إذا كان `BACKUP_DIR`, `logs/`, أو `mikrotik_bot.db` داخل مجلد قابل للمزامنة أو المشاركة.

### Operations

- إضافة أمر أو شاشة "System status" تعرض:
  - حالة Python/venv.
  - عدد الراوترات المحفوظة.
  - آخر backup.
  - آخر فشل watchdog.
  - حجم قاعدة البيانات والنسخ.
- جعل نتائج النسخ المجدول محفوظة في جدول مستقل بدلاً من الاعتماد على logs النصية فقط.
- إضافة retention واضح للسجلات والنسخ مع إمكانية ضبطه من Telegram.

### Testing

- الحفاظ على البوابة الحالية:
  - `ruff check . --select F821`
  - `scripts/validate_handlers.py`
  - `py_compile`
  - `pytest`
- إضافة اختبارات compatibility مركزة:
  - User Manager v6 profile/user fields.
  - User Manager v7 profile/user fields.
  - restore partial failure.
  - version cache invalidation.

## 6. المميزات المطلوبة لمدير الشبكة حسب الأولوية

### أولوية عالية

1. لوحة حالة لكل الراوترات
   - online/offline.
   - آخر فحص.
   - RouterOS version.
   - عدد Hotspot active.
   - آخر backup ناجح أو فاشل.

2. تنبيهات ذكية
   - انقطاع الراوتر وعودته.
   - فشل backup.
   - فشل اتصال API متكرر.
   - فشل restore أو reboot.

3. سجل تدقيق قابل للتصفية
   - حسب المشرف.
   - حسب الراوتر.
   - حسب العملية.
   - حسب التاريخ.

4. تحسين النسخ الاحتياطي
   - retention قابل للضبط.
   - عرض آخر نسخة لكل راوتر.
   - تحميل آخر backup مباشرة.
   - حفظ نتيجة كل job مجدول.

### أولوية متوسطة

5. تقارير Hotspot عملية
   - أكثر المستخدمين استهلاكاً.
   - مستخدمون بلا نشاط.
   - مستخدمون اقتربوا من الحد.
   - تصدير CSV/PDF.

6. أدوار داخل البوت
   - Owner/Admin كامل.
   - Operator للكروت والبحث فقط.
   - Viewer للتقارير فقط.

7. تحسين إدارة الكروت
   - دفعات batches بأسماء.
   - حالة بيع/استخدام.
   - إعادة طباعة batch.
   - بحث داخل batch.

### أولوية لاحقة

8. إعدادات توافق لكل راوتر
   - نوع User Manager path المحسوب.
   - آخر version معروف.
   - ملاحظات تشغيلية للراوتر.

9. واجهة تصدير ومزامنة
   - CSV للتقارير.
   - JSON للنسخ الإدارية.
   - أرشفة شهرية.

## 7. نتائج الفحوص الحالية

تم تشغيل الفحوص التالية على الحالة الحالية:

- `ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs --exclude _releases`: ناجح.
- `py -3.12 scripts\validate_handlers.py`: ناجح، وكل imports/registrations متسقة.
- `py -3.12 -m pytest -q`: ناجح، `652 passed`.

ملاحظة بيئة: تشغيل `python` المباشر تعثر بسبب مسار `uv`/صلاحيات WindowsApps، و`venv\Scripts\python.exe` يشير إلى Python غير موجود. المسار العملي المستخدم هو `py -3.12`.

## 8. الفجوات ذات الأولوية

1. توثيق وتشديد تشغيل `8728` بدون SSL.
2. إضافة مصفوفة توافق v6/v7 لأوامر User Manager والحقول المستخدمة في restore.
3. تحسين تجربة مدير الشبكة بلوحة حالة وتنبيهات وتقارير قابلة للتصدير.
4. إضافة أدوار داخل Telegram bot بدلاً من قائمة `ADMIN_IDS` فقط.
5. تخزين نتائج backup المجدول في جدول واضح مع retention.
6. تنظيف/عزل ملفات التشغيل المحلية: database، backups، logs، venv.

## 9. المصادر الخارجية

- python-telegram-bot `ConversationHandler`: https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html
- python-telegram-bot `ApplicationBuilder.concurrent_updates`: https://docs.python-telegram-bot.org/en/stable/telegram.ext.applicationbuilder.html#telegram.ext.ApplicationBuilder.concurrent_updates
- Telegram Bot API: https://core.telegram.org/bots/api
- MikroTik RouterOS API: https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API
