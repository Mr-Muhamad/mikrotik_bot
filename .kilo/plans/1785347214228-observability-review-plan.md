# Observability Framework Review & Improvement Plan

## السياق والهدف

مراجعة شاملة لإطار المراقبة (Observability) في مشروع بوت Telegram لإدارة MikroTik RouterOS، بهدف ضمان تتبع الطلبات من البداية للنهاية، وغنى السجلات بالسياق الكافي، وتصنيف الأخطاء بدقة، وتوحيد هيكل التنسيق ليتوافق مع متطلبات الإنتاج.

## التقييم الحالي

### 1. Traceability (القدرة على التتبع)

**الحالة الحالية:**
- يوجد `request_id` مبني على `ContextVar` عبر `utils/request_id.py`، ويُربط بـ `update.update_id` عند دخول الـ handler عبر `bind_request_id_from_update`
- الفلتر `RequestIdFilter` يُحقن الـ `request_id` في كل سجل log عبر `logging.Filter`
- formatter JSON في `logging_setup.py` يُضيف `request_id` كحقل مهيكل في كل دخول log

**الثغرات المكتشفة:**
- **الـ jobs الخلفية** (backup scheduler, watchdog, expiry check, stats snapshot) لا تحمل `request_id` — تُنفَّذ بواسطة `JobQueue` بدون ارتباط بـ `update_id`، لذلك كل السجلات تحمل القيمة الافتراضية `-`
- **لا يوجد نظام trace_id** يربط مجموعة من العمليات المرتبطة (مثل: callback → handler → execute → API call → response) تحت معرّف واحد يتجاوز الـ `request_id` الفردي
- **لا يوجد propagation لـ request_id في رسائل Telegram الموجهة للمستخدم** — المستخدم لا يستطيع الرجوع برقم البلاغ إلى السجلات بسهولة رغم أن `format_error_message` يُضيف `#<request_id>` في الرسالة، لكن لا يوجد ارتباط عكسي في السجلات لمعرفة أي تحديث أحدث هذا البلاغ
- **`run_blocking()`** ينسخ الـ `ContextVar` بشكل صحيح (`contextvars.copy_context()`)، لكن لا يوجد تأكيد log بأن السياق قد وُصل إلى الـ thread المنفذ

### 2. Contextual Richness (غنى السياق)

**الحالة الحالية:**
- JSON formatter يُخرج: `timestamp`, `level`, `logger`, `request_id`, `message`, `exception`, `stacktrace`
- بعض الموديولات تُضيف معلومات يدوياً في نص الرسالة (مثل `router_key` في `error_response.py`, `router_name` في `backup_scheduler.py`)
- `connection_pool.py` يُتابع مقاييس (attempts, successes, failures, cache_hits) لكنها غير مُسجَّلة في logs بشكل منظم

**الثغرات المكتشفة:**
- **غياب حقول مهيكلة في JSON**: لا يوجد `user_id`, `chat_id`, `router_key`, `command`, `duration_ms`, `success` كحقول منفصلة — كلها مدفوعة في نص `message` فقط
- **لا يوجد قياس المدة (duration)** لأي عملية API call أو handler أو service — لا يمكن تحديد نقاط الاختناق من السجلات
- **لا يوجد تتبع عدد النجاحات/الإخفاقات** بشكل مُهيكل لكل مكون
- **`_debug_log` في `mikrotik_api.py`** يُسجل kwargs في مستوى DEBUG فقط، ولا يُسجّل تنفيذ الأمر الفعلي في مستوى INFO
- **الـ `result` من أوامر API** لا يُسجَّل عند النجاح (حتى بشكل مُختصر) — لا يمكن معرفة كم مستخدم أو ما هي البيانات المُرجعة من السجلات

### 3. Error Granularity (دقة تصنيف الأخطاء)

**الحالة الحالية:**
- `error_response.py` يحتوي على نظام تصنيف أخطاء (`CATEGORY_CONNECTION`, `CATEGORY_AUTH`, `CATEGORY_TIMEOUT`, `CATEGORY_NOT_FOUND`, `CATEGORY_STORAGE`, `CATEGORY_GENERAL`)
- `classify_error()` يُصنّف exceptions إلى فئات واضحة
- `send_error()` يسجّل الخطأ بـ `logger.error()` مع نوع الخطأ ونصه المُنظّف

**الثغرات المكتشفة:**
- **التصنيف لا يُعكس في السجلات المهيكلية** — لا يوجد حقل `error_category` في JSON logs، كل information مضمنة في نص الرسالة فقط
- **لا يوجد ارتباط بين تصنيف الخطأ وإرسال التنبيه** — `send_error` يُرسل رسالة للمستخدم لكن لا يُفعّل أي آلية تنبيه إضافية (مثل إشعار للمشرفين عبر Telegram عند أخطاء النظام الحرجة)
- **أخطاء `LibRouterosError` في `mikrotik_api.py`** تُسجَّل بـ `exc_info=True` في بعض الأماكن وليس في أخرى — عدم اتساق في مستوى التفاصيل
- **`_execute_with_retry`** يُسجّل `All N attempts failed` في ERROR لكن لا يُفرّق بين خطأ الاتصال (connection) وخطأ الأمر نفس (command failure) — كلاهما يُسجَّل بنفس المستوى
- **أخطاء Telegram** (مثل `TelegramError` أثناء إرسال الرسائل) تُسجَّل في `_dispatch_message` لكن لا تُصنّف كخطأ نظامي قابل للمراقبة

### 4. Log Format Consistency (اتساق التنسيق)

**الحالة الحالية:**
- **Console handler**: `%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s`
- **JSON file handler**: حقول `timestamp`, `level`, `logger`, `request_id`, `message`, `exception`, `stacktrace`
- **لا يوجد tag للمكون** (مثل `[ROUTER]`, `[HANDLER]`, `[SERVICE]`, `[BACKUP]`) في أيٍّ من التنسيقين

**الثغرات المكتشفة:**
- **عدم وجود component/service tag** — من المستحيل تصفية سجلات مكون معين (مثلاً: عرض كل سجلات `mikrotik_api` فقط) بدون تحليل نص الرسالة
- **اتساق مستوى الـ logging**: بعض الموديولات تستخدم `logger.warning` لما يجب أن يكون `logger.error` (مثلاً `get_version` في `mikrotik_api.py` يفشل صراحةً لكن يستخدم `WARNING`)
- **`logging.getLogger(__name__)`** يُنتج أسماء logger مختلفة لكل موديول (مثلاً `core.mikrotik_api`, `utils.error_response`, `bot.handlers.watchdog`) — هذا جيد عملياً لكن لا يوجد توحيد لتسمية المكونات في السجلات
- **لا يوجد `structlog` أو `python-json-logger`** — الـ JSON formatter مُكتوب يدوياً ومفقود منه حقول مهمة (مثل `component`, `duration_ms`, `success`)
- **أسماء الـ logger** لا تتبع نمطاً موحداً — بعضها يستخدم `__name__` وبعضها يستخدم أسماء عشوائية

---

## التحسينات المقترحة

### الخاصة الأولى: إضافة component tag لهيكل الـ logging

**الهدف:** إضافة حقل `component` لكل دخول log ليُمكّن التصفية والتحليل الآلي.

**التنفيذ:**
1. تعريف ثوابت `COMPONENT_*` في `utils/logging_setup.py`:
   - `COMPONENT_HANDLER` — لمعالجات Telegram
   - `COMPONENT_ROUTER` — لطبقة MikroTik API و ConnectionPool
   - `COMPONENT_SERVICE` — للخدمات الخلفية (backup, scheduler, watchdog)
   - `COMPONENT_DATABASE` — لطبقة قاعدة البيانات
   - `COMPONENT_TELEGRAM` — لإرسال الرسائل عبر Telegram API
   - `COMPONENT_SYSTEM` — للنظام العام (config, startup, shutdown)

2. تعديل `RequestIdFilter` و `JsonFormatter` لإضافة حقل `component` من ContextVar
3. إنشاء context manager `bind_component(component: str)` في `utils/logging_setup.py` لتعيين component لكل scope
4. في `main.py` وكل handler، وضع `bind_component` عند نقاط الدخول المناسبة

### الخاصة الثانية: هيكلة ملفات السجلات مع حقول مهيكلية

**الهدف:** تحويل الـ JSON log entries من نصية إلى مهيكلية بالكامل.

**التنفيذ:**
1. إضافة حقول مهيكلية لـ `JsonFormatter`:
   ```json
   {
     "timestamp": "2026-07-29T21:54:06+03:00",
     "level": "INFO",
     "component": "ROUTER",
     "request_id": "a1b2c3d4e5f6",
     "message": "Executed command system/resource/print",
     "router_key": "discovered_42",
     "command": "system/resource/print",
     "duration_ms": 342,
     "success": true,
     "user_id": 123456789,
     "chat_id": 987654321
   }
   ```

2. إضافة حقل `duration_ms` لقياس وقت تنفيذ API calls في `mikrotik_api.py`:
   - في `_execute_with_retry`: قياس وقت التنفيذ الكلي وتسجيله
   - في `execute`, `execute_long`, `execute_non_blocking`: تسجيل البداية والنهاية

3. إضافة حقل `success` للعمليات:
   - `True` عند الإرجاع الطبيعي
   - `False` عند رفع exception

4. إضافة حقل `error_category` عند التصنيف في `error_response.py`:
   - `CONNECTION`, `AUTH`, `TIMEOUT`, `NOT_FOUND`, `STORAGE`, `GENERAL`

### الخاصة الثالثة: تحسين Traceability للـ background jobs

**الهدف:** ضمان أن كل عملية خلفية (job) لها `request_id` فريد و trace_id يربط خطواتها.

**التنفيذ:**
1. في `backup_scheduler.py`, `watchdog.py`, وكل job handler:
   - توليد `request_id` at job start via `new_request_id()`
   - وضعه في context via `bind_request_id()`
   - تسجيل بداية ونهاية كل خطوة

2. إضافة `trace_id` لربط العمليات المتسلسلة:
   - عند بدء handler لـ update معين → توليد `trace_id`
   - جميع الخطوات اللاحقة (API calls, DB queries, Telegram sends) تحمل نفس الـ `trace_id`
   - في JSON logs يمكن التصفية بـ `trace_id` لتجميع كل سجلات طلب واحد

3. إنشاء `trace_id` في `request_id.py` كـ ContextVar منفصل alongside `request_id`

### الخاصة الرابعة: تحسين Error Granularity و Notifications

**الهدف:** جعل الأخطاء قابلة للتصنيف الآلي والمراقبة والإشعارات.

**التنفيذ:**
1. إضافة حقل `error_category` في كل سجلات الخطأ:
   - تعديل `send_error` في `error_response.py` لتمرير `error_category` كمجال منظم في JSON log
   - إضافة `log_error()` helper يسجّل خطأ بـ `component`, `error_category`, `router_key`, `request_id`

2. إضافة تنبيه Telegram تلقائي لأخطاء حرجة:
   - أخطاء `CATEGORY_CONNECTION` و `CATEGORY_AUTH` المتكررة (>3 خلال 5 دقائق) تُرسل تنبيه لمشرفي Telegram
   - أخطاء `CATEGORY_STORAGE` تُرسل تنبيه فوري (مشكلة مساحة السيرفر)
   - إضافة `critical_error_callback` في `error_response.py` يُرسل رسالة لـ ADMIN_IDS

3. تطوير `error_response.py` ليدعم structured logging:
   - إضافة `log_error_details()` function تسجل كل شيء في JSON structured format
   - إضافة `error_context` dataclass يحتوي على: `router_key`, `command`, `user_id`, `chat_id`, `request_id`, `trace_id`, `attempt`, `duration_ms`

### الخاصة الخامسة: إضافة Duration Tracking لجميع العمليات الحرجة

**الهدف:** قياس أداء كل نقطة حرجة في النظام.

**التنفيذ:**
1. في `mikrotik_api.py` — `_execute_with_retry`:
   ```python
   start = time.monotonic()
   # ... execute ...
   duration_ms = (time.monotonic() - start) * 1000
   logger.info(f"Command {command} on {router_key} completed in {duration_ms:.1f}ms", extra={...})
   ```

2. في `connection_pool.py` — `get_connection`, `release_connection`:
   - تسجيل وقت انتظار الاتصال من الطابور
   - تسجيل عدد الاتصالات النشطة/الخاملة عند كل request

3. في `backup_scheduler.py` — `_backup_single_router`:
   - قياس مدة كل نوع backup (userman/full) وتسجيلها
   - تسجيل عدد الراوترات الناجحة/الفاشلة

4. في `callback_utils.py` — `safe_answer_callback`:
   - قياس وقت الإجابة على callback query

5. إضافة مقاييس في `core/metrics.py`:
   - `mikrotik_api_duration_seconds` (histogram by command and router)
   - `backup_duration_seconds` (histogram by backup type)
   - `error_count_total` (counter by error_category and component)
   - `request_latency_seconds` (histogram by handler)

### الخاصة السادسة: توحيد نمط الـ Log Messages عبر المشروع

**الهدف:** ضمان اتساق صياغة جميع الرسائل.

**التنفيذ:**
1. إنشاء `utils/log_helpers.py` مع دوال مساعدة:
   - `log_api_call(router_key, command, duration_ms, success, error=None)`
   - `log_handler_entry(handler_name, user_id, chat_id, command_text)`
   - `log_handler_exit(handler_name, duration_ms, success)`
   - `log_service_call(service_name, operation, duration_ms, success, error=None)`
   - `log_db_operation(operation, table, duration_ms, success, error=None)`

2. كل دالة تُنتج log entry بنفس البنية:
   ```
   [COMPONENT] OperationName key=value key=value duration=Xms success=bool
   ```

3. تحديث `AGENTS.md` لإضافة قاعدة أنه يجب استخدام هذه الدوال المساعدة بدلاً من `logger.info(f"...")` المباشرة عند وجود بيانات هيكلية

### الخاصة السابعة: تحسين Log Level Consistency

**الهدف:** تأكد أن مستوى التسجيل يعكس خطورة الحدث.

**التنفيذ:**
1. **ERROR**: عمليات فشلت بالكامل ولا يمكن المتابعة (connection refused after retries, backup failed for all routers, storage full)
2. **WARNING**: عمليات فشلت مؤقتاً أو فيها مخاطر لكن النظام يستمر (single router health check failed, API call timeout that will be retried, version unknown)
3. **INFO**: عمليات ناجحة مهمة (command executed, user action completed, backup finished, handler entered/exited)
4. **DEBUG**: تفاصيل داخلية (API kwargs, connection pool state, cache hits/misses, retry attempts)

5. مراجعة `mikrotik_api.py:217` (`get_version` يستخدم `WARNING` على فشل `execute_long`) — يجب أن يكون `ERROR` لأنه فشل حقيقي، لكن `WARNING` مقبول لأنه فشل ناعم (fallback لـ v6)

---

## خطة التنفيذ (مراحل)

### المرحلة 1: البنية التحتية (يوم 1)
- [ ] إضافة `component` context var و `bind_component()` في `utils/logging_setup.py`
- [ ] إضافة `trace_id` ContextVar و helpers في `utils/request_id.py`
- [ ] توسيع `JsonFormatter` لدعم الحقول المهيكلية الجديدة (`component`, `duration_ms`, `success`, `router_key`, `user_id`, `chat_id`, `command`, `error_category`, `trace_id`)
- [ ] إنشاء `utils/log_helpers.py` مع الدوال المساعدة المُوحدة

### المرحلة 2: طبقة MikroTik API (يوم 2)
- [ ] إضافة `duration_ms` و `success` tracking في `_execute_with_retry`
- [ ] إضافة `component=ROUTER` في كل log call في `mikrotik_api.py` و `connection_pool.py`
- [ ] تحديث `_debug_log` ليستخدم `log_api_call()` helper

### المرحلة 3: طبقة الأخطاء والإشعارات (يوم 3)
- [ ] إضافة `error_category` و structured logging في `error_response.py`
- [ ] إضافة critical error notification to Telegram admins في `send_error()`
- [ ] إضافة `error_context` dataclass

### المرحلة 4: Handlers و Jobs (يوم 4)
- [ ] إضافة `bind_component()` في `bot/registration_parts/` لكل handler
- [ ] إضافة `request_id` generation في `backup_scheduler.py`, `watchdog.py` jobs
- [ ] إضافة `trace_id` generation في handler entry points
- [ ] تحديث handler logging لاستخدام `log_helpers.py`

### المرحلة 5: Metrics و Monitoring (يوم 5)
- [ ] إضافة `duration_ms` metrics to `core/metrics.py` (histograms)
- [ ] إضافة `error_count_total` counter by component و error_category
- [ ] إضافة `mikrotik_api_duration_seconds` histogram
- [ ] إضافة `backup_duration_seconds` histogram

### المرحلة 6: التوثيق والتحقق (يوم 6)
- [ ] تحديث `AGENTS.md` بقواعد الـ logging الجديدة
- [ ] تحديث `scripts/validate_handlers.py` للتحقق من استخدام الدوال المساعدة
- [ ] تشغيل `ruff check .` و `pyright` للتحقق من صحة الكود
- [ ] تشغيل `pytest` للتحقق من عدم كسر الاختبارات

---

## مخاطر وملاحظات

1. **أداء JSON serialization**: إضافة حقول مهيكلية لجميع log calls قد يزيد حجم السجلات. يجب مراجعة `LOG_MAX_BYTES` و `LOG_BACKUP_COUNT` في `.env` إذا لزم الأمر.

2. **حساسية البيانات**: الحقول المهيكلية الجديدة (`router_key`, `user_id`, `chat_id`, `command`) قد تحتوي على معلومات يعتبرها البعض حساسة. يجب التأكد من فحص `SENSITIVE_API_FIELDS` و `_Secret_KEYWORDS` يغطي هذه الحقول.

3. ** backward compatibility**: السجلات القديمة لن تحتوي على الحقول الجديدة. أدوات التحليل (ELK, Loki, Grafana) يجب أن تتعامل مع غياب الحقول بهدوء.

4. **الإفراط في التسجيل (Log Spam)**: إضافة `trace_id` و `duration_ms` لكل log call قد ينتج كمية كبيرة من البيانات. يجب التأكد من أن مستوى DEBUG فقط هو الذي يحتوي التفاصيل الكاملة، بينما INFO يحتوي ملخصاً.

5. **Correlation with external monitoring**: يجب ربط المقاييس الجديدة (histograms, counters) مع dashboard Grafana إذا كان المشروع يستخدم واحدة.
