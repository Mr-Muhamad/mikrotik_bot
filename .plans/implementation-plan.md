# خطة التنفيذ — دفعات صغيرة مرتّبة
## MikroTik Telegram Bot — تحسينات الجودة + ميزات السوق

---

## نظرة عامة

التنفيذ مقسّم إلى 10 دفعات صغيرة مستقلة، كل دفعة قابلة للاختبار والمراجعة وحدها.
الترتيب: من الأكثر أثراً بأقل جهد إلى الأكثر تعقيداً.

**مبادئ التنفيذ:**
- كل دفعة تُعدَّل على ملفات محدودة وتُختبر بـ `validate_handlers.py` + `pytest`.
- لا تُعدَّل واجهات عامة دون تحديث كل مستدعيها في نفس الدفعة.
- أي migration للـ DB يُضاف في `init_db()` بنمط `_add_column_if_missing` الموجود.
- الـ bare `except:` في `common.py:68` يُعالج أولاً لأنه يخفي `SystemExit`.

---

## الدفعة 1 — إصلاح bare except + إضافة Lock لـ TTL Cache
**الملفات المتأثرة:** `bot/handlers/common.py`, `core/connection_pool.py`
**الاختبارات:** `pytest tests/core/test_connection_pool.py` + تشغيل يدوي للبوت

### Intent
- إصلاح `except:` الذي يخفي `SystemExit`/`KeyboardInterrupt`/`SIGTERM`.
- إضافة `threading.Lock` لـ `TTLCache` لأنها تُستخدم من threads متعددة عبر `ConnectionPool`.

### Expected Outcomes
- `bare except` لا يوجد في الكود.
- `TTLCache.get/set/invalidate/clear/__contains__` تعمل بأمان مع threads متعددة.
- الاختبارات الحالية لـ connection_pool تمر دون تعديل.

### Todo
- [ ] في `bot/handlers/common.py:68` — استبدل `except:` بـ `except Exception`
- [ ] في `core/connection_pool.py` — أضف `self._cache_lock = threading.Lock()` في `TTLCache.__init__`
- [ ] غلّف `get`, `set`, `invalidate`, `clear`, `__contains__`, `_evict_expired`, `__len__` بـ `with self._cache_lock:`
- [ ] شغّل `pytest tests/core/test_connection_pool.py -v`
- [ ] شغّل `python scripts/validate_handlers.py`

### Relevant Context
- `bot/handlers/common.py` السطر 66-69: الـ `except:` الحالي
- `core/connection_pool.py` السطور 26-79: كلاس `TTLCache`
- `ConnectionPool.__init__` يستخدم `threading.RLock` بالفعل للـ `self._lock` — لا تخلط بينهما
- `TTLCache` منفصلة عن `ConnectionPool._lock` وتحتاج lock خاصة بها

### Status: [ ] pending

---

## الدفعة 2 — توحيد Error Handling في الـ handlers
**الملفات المتأثرة:** `core/exceptions.py` (جديد), `core/mikrotik_api.py`, `bot/handlers/common.py`
**الاختبارات:** `pytest tests/ -v`

### Intent
إنشاء exception hierarchy بسيطة تُمكّن من تمييز أنواع الأخطاء وتسجيلها بـ context كافٍ (router_key, user_id).

### Expected Outcomes
- ملف `core/exceptions.py` يحتوي على: `RouterNotFoundError`, `RouterConnectionError`, `RouterCommandError`
- أي `logger.error` في handlers يتضمن `router_key` و `user_id` عند توفرهما
- لا يوجد `except Exception as e: logger.error(f"Failed: {e}")` بدون context

### Todo
- [ ] أنشئ `core/exceptions.py` بالأصناف: `MikrotikBotError(Exception)`, `RouterNotFoundError(MikrotikBotError)`, `RouterConnectionError(MikrotikBotError)`, `RouterCommandError(MikrotikBotError)`
- [ ] في `core/connection_pool.py` — ارفع `RouterNotFoundError` بدلاً من `ValueError` في `get_router_info()` عند عدم وجود الراوتر
- [ ] في `core/mikrotik_api.py` — ارفع `RouterCommandError` عند فشل الأوامر غير القابلة للإعادة
- [ ] في `bot/handlers/common.py` — أضف `user_id = update.effective_user.id` قبل أي `logger.error`
- [ ] شغّل `pytest tests/ -q`
- [ ] شغّل `ruff check . --select F821`

### Relevant Context
- `core/connection_pool.py:108` — `raise ValueError(f"Router '{router_key}' not configured...")`  ← يُستبدل بـ `RouterNotFoundError`
- `core/mikrotik_api.py` — `_execute_with_retry()` يرفع أخطاء `LibRouterosError` مباشرة
- لا تُغيّر signatures الدوال المُصدَّرة حتى لا تُكسر الـ tests الموجودة
- الـ `except (LibRouterosError, ConnectionError, OSError)` في `hotspot_manager.py` تبقى كما هي — هذه الدفعة فقط للـ exceptions الجديدة والـ logging

### Status: [ ] pending

---

## الدفعة 3 — نقل Watchdog State إلى SQLite
**الملفات المتأثرة:** `database/models.py`, `core/watchdog.py`, `bot/handlers/watchdog.py`
**الاختبارات:** `pytest tests/core/test_watchdog.py` + `pytest tests/bot/handlers/test_watchdog.py`

### Intent
الـ `_router_status` dict في الذاكرة يُمحى عند كل restart. نقله إلى جدول SQLite يحافظ على سجل الانقطاعات ويُمكّن عرضه تاريخياً.

### Expected Outcomes
- جدول `router_health_log(id, router_key, status, checked_at, error_msg)` في SQLite
- بعد restart البوت، `/watchdog` يعرض آخر حالة معروفة لكل راوتر من DB
- الـ `_router_status` dict يبقى كـ in-memory cache للسرعة، لكن يُزامَن مع DB

### Todo
- [ ] في `database/models.py` — أضف `CREATE TABLE IF NOT EXISTS router_health_log` في `init_db()` بالأعمدة: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `router_key TEXT NOT NULL`, `status TEXT NOT NULL` (online/offline), `checked_at DATETIME DEFAULT CURRENT_TIMESTAMP`, `error_msg TEXT DEFAULT ''`
- [ ] أضف index: `CREATE INDEX IF NOT EXISTS idx_health_router_time ON router_health_log(router_key, checked_at DESC)` في `_create_indexes()`
- [ ] أنشئ `database/repositories/router_health.py` بدوالي: `record_health(router_key, status, error_msg)` و `get_latest_health(router_key) -> dict | None` و `get_health_history(router_key, limit=10) -> list`
- [ ] في `core/watchdog.py` — عدّل `record_check_result()` ليستدعي `record_health()` بعد تحديث `_router_status`
- [ ] في `core/watchdog.py` — أضف `load_status_from_db()` تقرأ آخر نتيجة لكل راوتر وتملأ `_router_status` و`_last_known_status` — تُستدعى مرة عند startup
- [ ] في `main.py` — استدعِ `load_status_from_db()` في `post_init()` قبل تشغيل watchdog
- [ ] في `bot/handlers/watchdog.py` — عدّل عرض الحالة ليُضيف "آخر فحص" من DB
- [ ] شغّل `pytest tests/core/test_watchdog.py tests/bot/handlers/ -v`

### Relevant Context
- `core/watchdog.py` — `_router_status` و `_last_known_status` هما الـ dicts المستهدفة
- `main.py` — `post_init()` هو المكان المناسب لاستدعاء `load_status_from_db()`
- `database/models.py:68` — `_create_indexes()` لإضافة الـ index الجديد
- نمط الـ repositories الموجود في `database/repositories/` — اتبعه بدقة
- لا تُضف import دائري: `core/watchdog.py` يمكنه import من `database.repositories.router_health` بدون مشكلة

### Status: [ ] pending

---

## الدفعة 4 — تنبيهات انتهاء صلاحية مستخدمي Hotspot
**الملفات المتأثرة:** `core/hotspot_manager.py`, `core/backup_scheduler.py`, `bot/messages.py`
**الاختبارات:** `pytest tests/core/test_hotspot_manager.py -v`

### Intent
إرسال تنبيه يومي تلقائي للمشرف يعرض المستخدمين الذين تنتهي صلاحيتهم خلال 3 أيام.
هذه أعلى ميزة طلباً في سوق مزودي الإنترنت الصغار.

### Expected Outcomes
- `hotspot_manager.get_expiring_users(router_key, days=3)` تُعيد قائمة المستخدمين المشارفين على الانتهاء
- job يومي يعمل بعد backup job بـ 5 دقائق يرسل التقرير لـ ADMIN_IDS
- الرسالة تُنسَّق بوضوح: اسم المستخدم + تاريخ الانتهاء + البروفايل

### Todo
- [ ] في `core/hotspot_manager.py` — أضف `get_expiring_users(router_key, days=3) -> list[dict]`:
  - جلب `ip/hotspot/user/print` مع فلتر `.id`, `name`, `profile`, `limit-uptime`, `comment`
  - تحليل `limit-uptime` (صيغة RouterOS: `1d00:00:00`) ومقارنته مع تاريخ اليوم (مع `uptime` النشطة إن أمكن)
  - إعادة قائمة `{"name", "profile", "expires_in_days", "uptime_limit"}` للمستخدمين الذين `expires_in_days <= days`
  - عند فشل الجلب: أعد قائمة فارغة وسجّل `logger.warning` (لا ترفع exception)
- [ ] في `bot/messages.py` — أضف `EXPIRY_ALERT_HEADER`, `EXPIRY_ALERT_USER_ROW`, `EXPIRY_ALERT_EMPTY`
- [ ] في `core/backup_scheduler.py` — أضف `_do_expiry_check(context)` بنفس نمط `_do_backup`:
  - يجلب كل الروترات النشطة
  - يستدعي `get_expiring_users` لكل راوتر
  - يُرسل رسالة للـ ADMIN_IDS إذا وُجد مستخدمون منتهون
- [ ] في `BackupScheduler.start_daily()` — أضف `job_queue.run_daily(_do_expiry_check, ...)` بعد backup بـ 5 دقائق
- [ ] في `BackupScheduler.stop()` — أضف إيقاف expiry job
- [ ] شغّل `pytest tests/core/test_hotspot_manager.py -v`

### Relevant Context
- `core/hotspot_manager.py` — `add_user()` للاطلاع على كيفية استدعاء API
- `core/backup_scheduler.py` — نمط `_do_backup` يُستنسخ لـ `_do_expiry_check`
- RouterOS `limit-uptime` format: `"1d00:00:00"` = يوم واحد، `"0s"` = لا حد
- لا توجد قيمة "تاريخ انتهاء" مباشرة في RouterOS hotspot user — `limit-uptime` هو الحد الزمني الكلي
- **تحذير**: إذا كان `limit-uptime = "0s"` أو فارغاً، تجاهل المستخدم (لا حد زمني له)

### Status: [ ] pending

---

## الدفعة 5 — حظر MAC دائم
**الملفات المتأثرة:** `core/hotspot_manager.py`, `bot/handlers/hotspot_search.py`, `bot/keyboards.py`, `bot/messages.py`, `bot/handlers/callback_constants.py`, `bot/registrations.py`
**الاختبارات:** `pytest tests/core/test_hotspot_manager.py tests/bot/handlers/test_hotspot_search.py -v`

### Intent
تمكين المشرف من حظر جهاز بـ MAC address دائمياً في RouterOS address-list بدلاً من الطرد المؤقت فقط.

### Expected Outcomes
- زر "🚫 حظر دائم" يظهر في نتائج بحث الأجهزة بجانب زر "طرد"
- الحظر يضيف MAC لـ `/ip/hotspot/host/print` address-list أو `/ip/firewall/address-list`
- أمر `/blocked` يعرض قائمة الأجهزة المحظورة مع زر رفع الحظر

### Todo
- [ ] في `core/hotspot_manager.py` — أضف:
  - `block_mac(router_key, mac) -> bool`: يضيف MAC إلى `/ip/firewall/address-list` بـ `list=hotspot_blocked`
  - `unblock_mac(router_key, mac) -> bool`: يحذف بـ `find` ثم `remove`
  - `get_blocked_macs(router_key) -> list[dict]`: يجلب `/ip/firewall/address-list?list=hotspot_blocked`
- [ ] في `bot/handlers/callback_constants.py` — أضف في `CALLBACKS`: `"block_mac"`, `"unblock_mac"`, `"blocked_list"` وأضف builders: `block_mac_cb(mac)`, `unblock_mac_cb(mac)` وأضف PATTERNS المقابلة
- [ ] في `bot/keyboards.py` — عدّل `get_host_action_keyboard(host)` لتضيف زر "🚫 حظر" بجانب "طرد"، وأضف `get_blocked_macs_keyboard(macs, page)`
- [ ] في `bot/messages.py` — أضف `BLOCK_MAC_SUCCESS`, `BLOCK_MAC_FAIL`, `UNBLOCK_MAC_SUCCESS`, `BLOCKED_LIST_HEADER`, `BLOCKED_LIST_EMPTY`
- [ ] في `bot/handlers/hotspot_search.py` — أضف handlers: `block_mac_handler(update, context)`, `unblock_mac_handler(update, context)`, `show_blocked_list(update, context)`
- [ ] في `bot/registrations.py` — سجّل handlers الجديدة كـ `@standalone`
- [ ] شغّل `python scripts/validate_handlers.py`
- [ ] شغّل `pytest tests/ -q`

### Relevant Context
- `bot/handlers/hotspot_search.py` — `kick_host_handler` هو النمط المراد محاكاته
- `bot/handlers/callback_constants.py` — `CALLBACKS["kick_host"]` للاطلاع على pattern الحالي
- **تحذير RouterOS**: `address-list` في `/ip/firewall/address-list` تحتاج firewall rule منفصلة للحظر الفعلي — وثّق هذا في رسالة الحظر للمشرف
- استخدم `is_duplicate_callback()` في `block_mac_handler` لمنع الضغط المزدوج
- `get_blocked_macs` يُعيد قائمة فارغة عند أي خطأ — لا ترفع exception للمستخدم

### Status: [ ] pending

---

## الدفعة 6 — نظام الفواتير البسيط
**الملفات المتأثرة:** `database/models.py`, `database/repositories/card_batches.py`, `bot/handlers/batch.py`, `bot/keyboards.py`, `bot/messages.py`, `bot/handlers/callback_constants.py`, `bot/registrations.py`
**الاختبارات:** `pytest tests/database/ tests/bot/handlers/test_batch_handler.py -v`

### Intent
إضافة تتبع مبيعات الكروت: اسم العميل، تاريخ البيع، حالة الدفع، السعر — بدون تعقيد نظام محاسبة.

### Expected Outcomes
- عند إنشاء batch كروت، يُطرح سؤال اختياري: "اسم العميل؟ (أرسل . للتخطي)"
- كل batch له حالة دفع: مدفوع / غير مدفوع / مرحّل
- أمر `/sales` يعرض ملخص المبيعات الأسبوعية

### Todo
- [ ] في `database/models.py` — أضف في `migrate_card_batches_columns()`:
  - `customer_name TEXT DEFAULT ''`
  - `payment_status TEXT DEFAULT 'unpaid'`  (unpaid / paid / deferred)
  - `sale_price REAL DEFAULT 0`
  - `sold_at DATETIME`
- [ ] في `database/repositories/card_batches.py` — أضف:
  - `update_batch_payment(batch_id, status, customer_name, price)` 
  - `get_sales_summary(days=7) -> dict` — يعيد `{total_batches, paid_count, total_revenue, unpaid_count}`
- [ ] في `bot/handlers/callback_constants.py` — أضف `mark_paid_cb(batch_id)`, `mark_unpaid_cb(batch_id)` في CALLBACKS + PATTERNS
- [ ] في `bot/keyboards.py` — أضف `get_batch_payment_keyboard(batch_id, current_status)` بأزرار: مدفوع / غير مدفوع / مرحّل
- [ ] في `bot/messages.py` — أضف `SALES_SUMMARY_HEADER`, `SALES_WEEK_ROW`, `MARK_PAID_SUCCESS`
- [ ] في `bot/handlers/batch.py` — أضف:
  - `mark_batch_paid_handler(update, context)` 
  - `show_sales_summary(update, context)` ← handler لـ `/sales`
- [ ] في `bot/registrations.py` — سجّل handlers الجديدة + أضف `/sales` كـ CommandHandler standalone
- [ ] في `utils/bot_commands.py` — أضف `/sales` للقائمة السريعة
- [ ] شغّل `python scripts/validate_handlers.py`
- [ ] شغّل `pytest tests/database/ tests/bot/handlers/test_batch_handler.py -v`

### Relevant Context
- `database/repositories/card_batches.py` — `get_card_batches()` للاطلاع على نمط الاستعلام الحالي
- `bot/handlers/batch.py` — نمط معالجة الكروت الحالي
- `database/models.py:139` — `migrate_card_batches_columns()` هو المكان الصحيح للـ migration
- **تحذير**: `sold_at` يبقى NULL حتى تُحدَّث الحالة لـ "paid" — لا تضع DEFAULT CURRENT_TIMESTAMP
- لا تُعقّد: `sale_price` اختياري والمشرف يدخله يدوياً فقط عند الحاجة

### Status: [ ] pending

---

## الدفعة 7 — مشاركة كروت WiFi مع العميل
**الملفات المتأثرة:** `bot/handlers/batch.py`, `bot/keyboards.py`, `bot/messages.py`, `bot/handlers/callback_constants.py`, `bot/registrations.py`
**الاختبارات:** `pytest tests/bot/handlers/test_batch_handler.py -v`

### Intent
تمكين المشرف من إرسال بيانات اتصال WiFi مباشرة لعميله عبر Telegram بضغطة زر.

### Expected Outcomes
- زر "📤 إرسال للعميل" يظهر بجانب كل كرت في الـ batch
- عند الضغط، يُطلب إدخال Telegram user_id أو username للعميل
- تُرسل رسالة منسّقة للعميل تحتوي: SSID/DNS، اسم المستخدم، كلمة المرور، QR code اختياري

### Todo
- [ ] في `bot/handlers/callback_constants.py` — أضف `share_card_cb(batch_id, card_index)` و `PATTERNS["share_card"]`
- [ ] في `bot/keyboards.py` — أضف زر "📤 إرسال" في `get_batch_detail_keyboard(batch_id, card_index)` إذا وُجد هذا الـ keyboard، أو عدّل العرض الحالي
- [ ] في `bot/messages.py` — أضف `SHARE_CARD_PROMPT` (اطلب ID العميل), `SHARE_CARD_TEMPLATE` (رسالة العميل), `SHARE_CARD_SUCCESS`, `SHARE_CARD_FAIL`
- [ ] في `bot/handlers/batch.py` — أضف:
  - `share_card_start(update, context)` ← callback يحفظ `(batch_id, card_index)` في `user_data` ويطلب الـ ID
  - `share_card_send(update, context)` ← يستقبل نص، يحاول إرسال الكرت للعميل، ثم يعيد `ConversationHandler.END`
- [ ] في `bot/handlers/states.py` — أضف `WAITING_SHARE_RECIPIENT` في `WaitingState`
- [ ] في `bot/registrations.py` — سجّل callback + state جديد في main conversation
- [ ] شغّل `python scripts/validate_handlers.py`

### Relevant Context
- `bot/handlers/batch.py` — النمط الحالي لعرض تفاصيل الكروت
- الرسالة للعميل تكون نصية فقط (بدون PDF) — سريعة وبسيطة
- **تحذير**: استخدم `try/except` عند إرسال للعميل: قد يكون الـ ID خاطئاً أو المستخدم حظر البوت
- **تحذير**: لا تُرسل كلمة المرور إن كانت فارغة — أرسل "لا كلمة مرور" بدلاً منها
- إذا كانت إعدادات PDF تحتوي DNS/SSID — ضمّنها في رسالة العميل

### Status: [ ] pending

---

## الدفعة 8 — استخراج factory لدوال "الرجوع" المتكررة
**الملفات المتأثرة:** `bot/handlers/handler_utils.py`, وكل handlers التي تحتوي دوال back متطابقة
**الاختبارات:** `pytest tests/bot/ -v`

### Intent
إزالة التكرار في 50+ دالة back handler عبر factory function واحدة.

### Expected Outcomes
- `make_back_step(message_key, keyboard_fn, next_state)` في `handler_utils.py`
- الدوال المتكررة تُستبدل بـ `handler = make_back_step(...)`
- السلوك لا يتغير — فقط تقليل الكود المكرر

### Todo
- [ ] في `bot/handlers/handler_utils.py` — أضف:
  ```python
  def make_back_step(message: str, keyboard_fn, next_state: int):
      async def _handler(update, context):
          query = update.callback_query
          await safe_answer_callback(query)
          chat_id = update.effective_chat.id
          await send_and_track(context, chat_id, message, keyboard_fn())
          return next_state
      return _handler
  ```
- [ ] حدّد كل دوال "back" في `hotspot_add.py`, `hotspot_edit.py`, `hotspot_cards.py`, `userman.py` التي تتبع نفس النمط
- [ ] استبدل كل دالة متطابقة بـ `factory_fn = make_back_step(MSG, keyboard_fn, STATE)`
- [ ] تأكد من تسجيل الـ handlers الجديدة في `registrations.py` بنفس المفاتيح القديمة
- [ ] شغّل `python scripts/validate_handlers.py`
- [ ] شغّل `pytest tests/bot/ -v`

### Relevant Context
- `bot/handlers/hotspot_add.py` — ابحث عن دوال `back_to_*`
- `bot/handlers/hotspot_edit.py` — نفس النمط
- `utils/callback_utils.py` — `safe_answer_callback` موجود
- **تحذير**: بعض دوال "back" تُعدّل `context.user_data` قبل الإرجاع — تحقق من كل دالة قبل استبدالها
- **تحذير**: لا تستبدل دوال back التي تحتوي منطق إضافي (مثل تنظيف الحالة أو جلب بيانات) — فقط الدوال النقية

### Status: [ ] pending

---

## الدفعة 9 — إحصائيات تاريخية (Snapshots)
**الملفات المتأثرة:** `database/models.py`, `core/stats.py`, `core/backup_scheduler.py`, `bot/handlers/stats.py`, `bot/messages.py`
**الاختبارات:** `pytest tests/core/test_stats.py tests/bot/handlers/test_hotspot_stats_handler.py -v`

### Intent
حفظ snapshot يومي لإحصائيات كل راوتر ليُمكن عرض مقارنة أمس/اليوم وآخر 7 أيام.

### Expected Outcomes
- جدول `stats_snapshots(router_key, snapshot_date, active_users, total_users, bytes_in, bytes_out)`
- `/stats` يعرض: البيانات الحالية + مقارنة بالأمس (↑↓ فرق المستخدمين والبيانات)
- آخر 7 أيام تُعرض كـ ASCII bar chart نصي بسيط

### Todo
- [ ] في `database/models.py` — أضف `CREATE TABLE IF NOT EXISTS stats_snapshots` في `init_db()` بالأعمدة: `id, router_key, snapshot_date DATE, active_users INTEGER, total_users INTEGER, bytes_in INTEGER DEFAULT 0, bytes_out INTEGER DEFAULT 0`
- [ ] أضف index: `idx_snapshots_router_date ON stats_snapshots(router_key, snapshot_date DESC)`
- [ ] أنشئ `database/repositories/stats_snapshots.py` بدوالي: `save_snapshot(router_key, data)`, `get_yesterday_snapshot(router_key)`, `get_week_snapshots(router_key) -> list`
- [ ] في `core/backup_scheduler.py` — أضف `_do_stats_snapshot(context)` يجلب الإحصائيات الحالية ويحفظها
- [ ] في `core/stats.py` — أضف `get_week_trend(router_key) -> list[dict]` تقرأ من DB
- [ ] في `bot/handlers/stats.py` — عدّل `stats_hotspot()` ليعرض المقارنة مع الأمس والـ trend الأسبوعي
- [ ] في `bot/messages.py` — أضف `STATS_TREND_HEADER`, `STATS_TREND_ROW`, `STATS_VS_YESTERDAY`
- [ ] شغّل `pytest tests/core/test_stats.py -v`

### Relevant Context
- `core/stats.py` — `get_hotspot_stats()` هو مصدر البيانات الحالية
- `core/backup_scheduler.py` — نمط `_do_backup` للـ daily job
- **تحذير**: `bytes_in/bytes_out` في RouterOS hotspot قد تكون بالـ bytes أو نصاً — استخدم `parse_bytes()` من `utils/formatters.py`
- **تحذير**: إذا كانت `stats_snapshots` فارغة (أول يوم)، أظهر البيانات الحالية فقط بدون مقارنة
- ASCII chart بسيط: كل يوم صف = `"يوم | ████ 45 مستخدم"`

### Status: [ ] pending

---

## الدفعة 10 — Tenant Isolation للمشغلين
**الملفات المتأثرة:** `database/models.py`, `database/repositories/admin_roles.py`, `utils/admin_decorator.py`, `bot/handlers/roles.py`, `bot/keyboards.py`
**الاختبارات:** `pytest tests/utils/test_admin_decorator.py tests/database/ -v`

### Intent
كل مشغل (operator/viewer) يرى ويدير فقط الروترات المخصصة له — دون تغيير سلوك الـ admin الكامل.

### Expected Outcomes
- جدول `operator_router_permissions(operator_id, router_id)` في SQLite
- `get_user_routers(user_id)` تُعيد روترات المستخدم فقط (للـ admin: كل الروترات)
- Admin يستطيع تخصيص راوتر لمشغل عبر واجهة `/roles`

### Todo
- [ ] في `database/models.py` — أضف `CREATE TABLE IF NOT EXISTS operator_router_permissions` في `init_db()`: `operator_id INTEGER NOT NULL, router_id INTEGER NOT NULL, assigned_by INTEGER, assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (operator_id, router_id)`
- [ ] في `database/repositories/admin_roles.py` — أضف: `assign_router_to_operator(operator_id, router_id, assigned_by)`, `revoke_router_from_operator(operator_id, router_id)`, `get_operator_routers(operator_id) -> list[int]`, `is_operator_allowed(operator_id, router_id) -> bool`
- [ ] في `bot/router_selector.py` — عدّل `get_user_routers(user_id)` لتستدعي `get_operator_routers()` إذا لم يكن المستخدم admin
- [ ] في `utils/admin_decorator.py` — أضف تحقق في `@require_router` أن المستخدم مسموح له بهذا الراوتر
- [ ] في `bot/handlers/roles.py` — أضف واجهة لإسناد الروترات: `assign_router_to_operator_handler`
- [ ] في `bot/keyboards.py` — أضف `get_operator_router_assignment_keyboard(routers, assigned)`
- [ ] شغّل `python scripts/validate_handlers.py`
- [ ] شغّل `pytest tests/ -q`

### Relevant Context
- `utils/admin_decorator.py` — `@admin_only` و `@require_role` للاطلاع على نمط الـ decorator
- `bot/router_selector.py` — `get_user_routers()` و `get_selected_router()` هما نقطتا التعديل
- `database/repositories/admin_roles.py` — نمط CRUD الحالي
- **تحذير**: admin (ADMIN_IDS) لا يخضع لـ operator_router_permissions أبداً — تحقق من الـ ADMIN_IDS أولاً
- **تحذير**: إذا لم يكن للـ operator أي روتر مخصص، أظهر رسالة "لا توجد روترات مخصصة لك"

### Status: [ ] pending

---

## ترتيب الأولويات المرئي

```
الدفعة 1  [bare except + Cache Lock]     ← دقيقة / أثر فوري على الاستقرار
الدفعة 2  [Exception Hierarchy]           ← يوم / يُحسّن الـ debugging
الدفعة 3  [Watchdog → DB]                ← يوم / لا تُضيع سجل الانقطاعات
الدفعة 4  [تنبيهات انتهاء الاشتراك]     ← يوم / أعلى طلب في السوق
الدفعة 5  [حظر MAC]                      ← يوم / مطلوب من كل مشغل
الدفعة 6  [نظام الفواتير]               ← يومان / تجاري عالي
الدفعة 7  [مشاركة كروت للعميل]          ← يوم / تجاري متوسط
الدفعة 8  [Factory لدوال Back]           ← يومان / جودة كود
الدفعة 9  [إحصائيات تاريخية]            ← يومان / قيمة إدارية
الدفعة 10 [Tenant Isolation]             ← أسبوع / للمؤسسات
```

---

## Quality Gate لكل دفعة (إلزامي قبل الانتقال للتالية)

```bash
ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs --exclude _releases
py -3.12 scripts/validate_handlers.py
py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"
py -3.12 -m pytest -q
```

---

## ملاحظات عامة لكل الدفعات

1. **لا تُعدّل واجهة دالة موجودة** دون تحديث كل مستدعيها في نفس الدفعة.
2. **أي جدول DB جديد** يُضاف عبر `CREATE TABLE IF NOT EXISTS` في `init_db()` — لا تُنشئ `ALTER TABLE` منفردة.
3. **أي callback_data جديد** يُعرَّف أولاً في `CALLBACKS/PATTERNS` ثم يُستدعى بالاسم في `registrations.py`.
4. **النصوص العربية** توضع في `bot/messages.py` حصراً.
5. **الأخطاء من RouterOS** لا تظهر للمستخدم — تُسجَّل بـ `logger.error` وتُرسل رسالة عامة فقط.
