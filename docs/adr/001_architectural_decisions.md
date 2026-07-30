# Architecture Decision Records (ADR)

سجل القرارات المعمارية لتأصيل الاختيارات البرمجية الكبرى في بنية MikroTik Telegram Bot.

---

## 📄 ADR 001: فصل طبقة التفاعل عن النواة (Presentation vs Core Isolation)

- **الحالة:** مُعتمد (Accepted)
- **السياق:** في البداية كان كود اتصال ميكروتيك متداخلاً مع معالجات رسائل تليجرام في ملفات الـ Handlers.
- **القرار المعماري:**
  1. عزل مجلد `core/` ليعمل كـ Pure Python Services دون أي استيراد لمكتبات تليجرام (`python-telegram-bot`).
  2. حصر كافة تفاعلات Telegram UI والأزرار وتنظيف الشات داخل مجلد `bot/`.
- **النتيجة والتأثير:** إمكانية إعادة استخدام خدمات ميكروتيك في أي تطبيق مستقبلي (Web/Mobile App) بسلامة تامة وسهولة اختبار المكونات بصورة مستقلة.

---

## 📄 ADR 002: استراتيجية إدارة اتصالات ميكروتيك (Connection Pooling & Thread Safety)

- **الحالة:** مُعتمد (Accepted)
- **السياق:** فتح اتصال ميكروتيك جديد لكل استعلام كان يستهلك معالج الراوتر ويتسبب في بطء الاستجابة.
- **القرار المعماري:**
  1. إنشاء `ConnectionPool` يحدد `MAX_CONNECTIONS_PER_ROUTER = 3`.
  2. حظر العمليات المكثفة داخل الـ Event Loop بالاستعانة بـ `run_blocking` وتمرير المهام لـ ThreadPoolExecutor بحجم متوازن `max_workers = 15`.
- **النتيجة والتأثير:** استجابة خاطفة وحماية معالج ميكروتيك والسيرفر من الاستنزاف مع تفادي تعليق واجهة Telegram.

---

## 📄 ADR 003: حراسة وتتبع أزرار الـ Callbacks (Callback Query Ack & Dedup)

- **الحالة:** مُعتمد (Accepted)
- **السياق:** كانت الأزرار تظهر متجمدة عند الضغط المزدوج أو التفاعل مع القوائم القديمة.
- **القرار المعماري:**
  1. تقديم `safe_answer_callback` لتكون في أول سطر من أي معالج تفاعلي.
  2. تسجيل معالج وقائي شامل بـ Pattern `^.*$` في ختام سجل المعالجات لالتقاط وتنبيه المستخدم بالأزرار المنتهية.
- **النتيجة والتأثير:** منع تجمد الواجهة نهائياً واستجابة فورية لكافة نقرات الأزرار.

---

## 📄 ADR 004: نظام المراقبة والمقاييس (Observability & Metrics)

- **الحالة:** مُعتمد (Accepted)
- **السياق:** لم يكن هناك أي تتبع موحّد لأداء النظام—أداء الاتصالات، استعلامات قاعدة البيانات، طلبات MikroTik API، ومدة معالجة Telegram كانت جميعها غير مرئية. كان تشخيص المشاكل يتطلب تخميناً بدلاً من أدلة.
- **القرارات المعمارية:**
  1. **Prometheus endpoint** (`core/metrics.py`): توحيد جميع المقاييس في `/metrics` باستخدام `prometheus_client` مع 11 metric (counters, histograms, gauges).
  2. **ContextVars للتتبع** (`utils/logging_setup.py`): حقن `user_id`, `chat_id`, `router_key`, `command`, `success`, `duration_ms`, `error_category` و `component` في كل سجل وكل metric عبر ContextVar.
  3. **توقيت DB** (`database/execute.py`): `timed_execute()` يغلف استعلامات SQLite مع تسجيل تلقائي للمدة وعدد الصفوف وضخ `record_db_query()`.
  4. **توقيت API خارجي** (`utils/log_helpers.py`): `log_api_call()` كـ decorator/context manager لتسجيل وتوقيت استدعاءات MikroTik API و Telegram API.
  5. **صحة المكونات** (`get_health_status`, `get_error_rate`): sliding window لكل مكون، عتبات 10% (منحط) و25% (حرج)، مع `bot_health_status` و `bot_error_rate` gauges.
  6. **ربط في طبقة المعالجات** (`utils/handler_registry.py`): `_wrapped_handler` تسجل `record_telegram_request()` مع النجاح/الفشل وتوقيت المعالجة.
- **النتيجة والتأثير:** رؤية كاملة لأداء النظام في الوقت الحقيقي عبر `/metrics`. تشخيص المشاكل يستند الآن إلى مقاييس موضوعية بدلاً من التخمين. فتح الباب لتنبيهات استباقية (Alerting) عبر Prometheus.
