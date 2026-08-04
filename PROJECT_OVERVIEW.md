# MikroTik Telegram Bot - Project Overview

## 1. الغرض
بوت Telegram عربي لإدارة روترات MikroTik RouterOS. يتيح للمشرفين إدارة مستخدمي Hotspot، إنشاء كروت PDF للطباعة، إدارة User Manager، اكتشاف الروترات وإضافتها يدوياً، النسخ الاحتياطي والاستعادة، مراقبة حالة الروترات (Watchdog)، إعدادات PDF، دفعات الكروت والمبيعات، سجل التدقيق، وتقارير الإحصائيات — كل ذلك عبر واجهة Telegram موحدة وآمنة.

## 2. الهيكلية المعمارية
- **الواجهة:** مكتبة `python-telegram-bot` (الإصدار 21+) مع `ConversationHandler` رئيسي لإدارة تدفقات المحادثة متعددة الخطوات، مدعومة بنماذج بيانات `Dataclasses` (`bot/handlers/session_models.py`) لضمان سلامة النوعية، مع `concurrent_updates(False)` لاستقرار الـ FSM.
- **التسجيل المركزي:** كل المعالجات والأزرار تُسجَّل مركزيّاً في `bot/registrations.py` عبر `bot/registration_parts/`، ويُبنى التطبيق عبر `utils/handler_registry.py`. لا يُسجَّل أي معالج يدوياً في `main.py`.
- **التواصل مع الراوتر:** بروتوكول MikroTik API عبر `librouteros` على منفذ `8728` (أو المخصص)، من خلال `core/mikrotik_api.py` مع connection pool وretry وtimeouts، وحماية عبر `core/circuit_breaker.py` وقفل كتابة لكل راوتر.
- **قاعدة البيانات:** SQLite مع نظام ترحيل `Alembic` (`alembic/`). تُحفظ الروترات المكتشفة وجلسات المستخدمين، وتُشفَّر كلمات السر بـ `Fernet` عبر `utils/crypto.py`. الوصول للبيانات عبر Repository Pattern في `database/repositories/`.
- **طبقة الخدمات:** منطق الأعمال في `core/` معزول عن Telegram قدر الإمكان، وموزع بوحدات متخصصة (Hotspot، User Manager، Backup، Reports، Stats، Watchdog).
- **المراقبة:** مقاييس Prometheus في `core/metrics.py` تُصدَر عبر `/metrics` مع حالة صحة المكونات ومعدل الخطأ، وتتبُّع طلبات عبر `request_id` في `utils/logging_setup.py`.

### بنية الملفات الرئيسية
- `bot/handlers`: معالجات الأوامر والنصوص، مع `router_flows/` لتدفقات الروترات، و`common/` للقوائم العامة.
- `bot/keyboards/`: حزمة منفصلة لكل مجموعات أزرار InlineKeyboard (Hotspot، Router، Operator، Reports، Settings، Userman، Common).
- `bot/messages.py`: مركز تخزين رسائل البوت (دعم اللغة العربية).
- `bot/router_selector.py`: حالة الراوتر المختار لكل مستخدم.
- `core/`: طبقة الخدمات (MikroTik API، النسخ الاحتياطي، المراقبة، الإحصائيات، توليد التقارير).
- `database/repositories`: مستودعات CRUD لكل جدول.
- `utils/`: أدوات مساعدة (الحماية، التحقق، التنسيق، التشفير، السجلات، الترقيم).
- `pdf/`: توليد PDF للكروت مع دعم العربية وQR Code.
- `docs/`: توثيق أمني وتوافق (RouterOS API security، توافق v6/v7).
- `tests/`: اختبارات pytest تغطي الوحدات والتكامل والحالات الفشلية والتزامن.

## 3. الملامح الرئيسية الحالية
- إدارة Hotspot كاملة: إضافة، تعديل، حذف، بحث، طرد أجهزة، حظر MAC، تقرير استخدام.
- إدارة User Manager (متوافق مع RouterOS v6/v7) مع مزامنة البروفايلات وكاشها.
- اكتشاف الروترات عبر MNDP/ARP ومسح المنافذ، وإضافتها يدوياً مع اختبار الاتصال.
- إنشاء كروت Hotspot وUser Manager بصيغة PDF (عربي + QR) مع إعدادات PDF قابلة للتعديل.
- النسخ الاحتياطي والاستعادة (System / User Manager) مع جدولة يومية ورفع عبر FTP وخادم ملفات.
- مراقبة حالة الروترات (Watchdog) مع تنبيهات الانقطاع والعودة.
- أدوار المشرفين: super_admin / admin / operator / viewer / customer مع صلاحيات مشغّلين وربطهم بالروترات.
- دفعات الكروت مع ملخص المبيعات وإدارة حالات الدفع.
- تقارير Hotspot/User Manager مع تصدير CSV وExcel ورسوم بيانية.
- سجل تدقيق `/logs` للعمليات الحساسة مع فلاتر وترقيم صفحات.
- حماية الجلسات: فصل تلقائي عند الخمول مع أمر `/timeout` لتخصيص المدة.
- مقاييس Prometheus ومراقبة صحة المكونات عبر `/metrics`.

## 4. معايير الجودة
- Pyright (strict): صفر أخطاء. Ruff: صفر أخطاء. Pytest: نجاح كامل (~3,000 اختبار) بتغطية ≥ 80%.
- فحص المعالجات والـ callbacks عبر `scripts/validate_handlers.py` و`scripts/validate_routeros_paths.py` و`scripts/check_type_ignore.py`.
- سياسة عدم تسريب البيانات الحساسة في السجلات أو رسائل الخطأ.

## 5. مسار التطوير المستقبلي
- إضافة دعم اللغات المتعددة بسهولة بفضل مركزة الرسائل في `bot/messages.py`.
- توسيع تقارير المبيعات والإحصائيات عبر لوحة تفاعلية.
- تعزيز أتمتة النسخ الاحتياطي بحلول تخزين سحابية اختيارية.
