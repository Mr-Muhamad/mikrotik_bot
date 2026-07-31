# دليل التحسينات الشامل — MikroTik Telegram Bot

> **تاريخ الإعداد:** 2026-07-22
> **الإصدار:** 1.0
> **التقييم الحالي:** 8.5/10
> **المحرر:** Claude Code (big-pickle)

---

## جدول المحتويات

1. [نظرة عامة](#1-نظرة-عامة)
2. [المرحلة الأولى: إصلاحات حرجة](#2-المرحلة-الأولى-إصلاحات-حرجة)
3. [المرحلة الثانية: تحسينات عالية](#3-المرحلة-الثانية-تحسينات-عالية)
4. [المرحلة الثالثة: تحسينات متوسطة](#4-المرحلة-الثالثة-تحسينات-متوسطة)
5. [المرحلة الرابعة: تنظيف وتوثيق](#5-المرحلة-الرابعة-تنظيم-وتوثيق)
6. [جدول الأولوية النهائي](#6-جدول-الأولوية-النهائي)
7. [مراجع التحليل](#7-مراجع-التحليل)

---

## 1. نظرة عامة

| المؤشر | القيمة |
|---|---|
| **ملفات المصدر** | 126 ملف `.py` |
| **أسطر الكود** | 18,404 سطر |
| **ملفات الاختبار** | 68 ملف |
| **اختبارات ناجحة** | 818 اختبار (100%) |
| **Ruff violations** | صفر (E, F, W, I, UP, B) |
| **استيرادات دائرية** | صفر |
| **التقييم الحالي** | **8.5/10** |

### الأهداف المرجوة بعد التنفيذ

| المعيار | قبل | بعد (المتوقع) |
|---|---|---|
| الأمان | 8.5/10 | 9.5/10 |
| معالجة الأخطاء | 7.5/10 | 9/10 |
| الأداء | 8/10 | 9/10 |
| جودة الكود | 8/10 | 9/10 |
| **التقييم العام** | **8.5/10** | **9.2/10** |

---

## 2. المرحلة الأولى: إصلاحات حرجة

> **المدة المقدرة:** 3-5 أيام
> **المخاطر:** منخفضة — إصلاحات موضعية لا تغير المعمارية

---

### 2.1 — إصلاح `validate_mac` bug

| التفصيل | |
|---|---|
| **الموقع** | `utils/validators.py:75` + `core/hotspot_blocking.py:22` |
| **المشكلة** | `validate_mac()` تُعيد `tuple[bool, str]` لكن `block_mac()` تستدعي `if not validate_mac(mac)` |
| **النتيجة** | الـ tuple دائماً `True` (حتى لو كان الـ MAC خاطئاً)، أي MAC يُضاف إلى firewall |
| **التأثير** | ثغرة أمنية — السماح بعناوين MAC غير صالحة بالدخول إلى قائمة الحظر |

**الكود الحالي (`core/hotspot_blocking.py:20-24`):**

```python
from utils.validators import validate_mac

if not validate_mac(mac):          # ← خطأ: tuple دائماً True
    logger.warning(f"Invalid MAC address format rejected in block_mac: {mac!r}")
    return False
```

**الكود المُصحح:**

```python
from utils.validators import validate_mac

is_valid, result = validate_mac(mac)
if not is_valid:
    logger.warning(f"Invalid MAC address: {result}")
    return False
mac = result  # استخدام القيمة المُنظّفة (AA:BB:CC:DD:EE:FF)
```

**نقاط الاستدعاء المتأثرة:**
- `core/hotspot_blocking.py:22` — `block_mac()`
- يجب البحث عن أي استدعاء آخر لـ `validate_mac` في `core/hotspot_manager.py`

**خطوات التحقق:**
```bash
py -3.12 -m pytest tests/ -k mac -v
```

---

### 2.2 — إصلاح مقارنة uptime النصية

| التفصيل | |
|---|---|
| **الموقع** | `core/hotspot_manager.py:421` |
| **المشكلة** | مقارنة `uptime` كنص بدلاً من رقم |
| **التأثير** | خلل منطقي في تحديد المستخدمين غير النشطين |

**الكود الحالي:**
```python
if user.get("uptime") == "00:00:00":
    # المستخدم غير نشط
```

**الكود المُصحح:**
```python
def _parse_uptime_seconds(uptime_str: str) -> int:
    """ تحويل uptime من RouterOS (D+hh:mm:ss) إلى ثوانٍ """
    import re
    total = 0
    days = re.search(r"(\d+)\+", uptime_str)
    if days:
        total += int(days.group(1)) * 86400
    parts = uptime_str.split("+")[-1].split(":")
    if len(parts) == 3:
        total += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return total

# الاستخدام:
if _parse_uptime_seconds(user.get("uptime", "00:00:00")) == 0:
    pass  # المستخدم غير نشط
```

---

### 2.3 — إصلاح `time.sleep` الحا.blocking

| التفصيل | |
|---|---|
| **الموقع** | `core/connection_pool.py:98` + `core/mikrotik_api.py:158` |
| **المشكلة** | `time.sleep()` في سياق async يحجب event loop |
| **التأثير** | تجميد البوت بالكامل أثناء الانتظار |

**الموقع الأول (`connection_pool.py:97-98`):**

```python
# كان:
if attempt < MAX_RETRIES:
    time.sleep(RETRY_DELAY)  # ← يحجب الخيط

# يجب أن يكون (إذا كان السياق async):
if attempt < MAX_RETRIES:
    import asyncio
    await asyncio.sleep(RETRY_DELAY)

# أو (إذا كان sync فقط):
from utils.async_blocking import run_blocking
await run_blocking(lambda: time.sleep(RETRY_DELAY))
```

**الموقع الثاني (`mikrotik_api.py:157-158`):**

```python
# _throttle() تستدعي time.sleep(sleep_needed)
# يجب التحقق من السياق: هل تُستدعى من async؟
# إذا نعم → asyncio.sleep
# إذا لا → time.sleep مقبول (في run_blocking executor)
```

**خطوات التحقق:**
```bash
py -3.12 -m pytest tests/ -k connection -v
```

---

### 2.4 — تحسين `classify_error()` لدعم أنواع أخطاء إضافية

| التفصيل | |
|---|---|
| **الموقع** | `utils/error_response.py:88-111` |
| **المشكلة** | لا يتعرف على `TimeoutError`, `socket.timeout`, `httpx.TimeoutException` |
| **التأثير** | أخطاء المهلة تُعامل كأخطاء عامة بدلاً من أخطاء اتصال |

**الكود المُضاف (قبل `return CATEGORY_GENERAL`):**

```python
def classify_error(error: Exception) -> str:
    # ... (الكود الحالي)

    # إضافة دعم TimeoutError و socket.timeout
    if isinstance(error, (TimeoutError, OSError)):
        msg = str(error).lower()
        if "timed out" in msg or "timeout" in msg:
            return CATEGORY_TIMEOUT
        if isinstance(error, OSError):
            if any(kw in msg for kw in ("refused", "closed", "reset", "unreachable")):
                return CATEGORY_CONNECTION

    # دعم httpx إذا كان متاحاً
    try:
        import httpx
        if isinstance(error, httpx.TimeoutException):
            return CATEGORY_TIMEOUT
        if isinstance(error, httpx.ConnectError):
            return CATEGORY_CONNECTION
    except ImportError:
        pass

    return CATEGORY_GENERAL
```

---

## 3. المرحلة الثانية: تحسينات عالية

> **المدة المقدرة:** 5-8 أيام
> **المخاطر:** منخفضة-متوسطة

---

### 3.1 — Rate Limit مخصص حسب نوع الأمر

| التفصيل | |
|---|---|
| **الموقع** | `utils/admin_decorator.py:31` |
| **المشكلة** | `RATE_LIMIT_WINDOW = 1.0` — واحد لكل الأوامر |
| **التأثير** | لا يوجد حماية إضافية للأوامر الخطيرة مثل reboot و restore |

**الكود المقترح:**

```python
# admin_decorator.py — أعلى الملف:
RATE_LIMITS: dict[str, float] = {
    "default": 1.0,
    "reboot": 10.0,
    "backup": 30.0,
    "restore": 60.0,
    "delete": 5.0,
    "add_user": 2.0,
    "edit_user": 2.0,
}

def _get_rate_limit(func_name: str) -> float:
    for key, limit in RATE_LIMITS.items():
        if key in func_name:
            return limit
    return RATE_LIMITS["default"]
```

**تحديث `_check_rate_limit`:**
```python
def _check_rate_limit(user_id: int, func_name: str = "") -> bool:
    limit = _get_rate_limit(func_name)
    # ... (تعديل المنطق ليستخدم limit بدلاً من RATE_LIMIT_WINDOW)
```

---

### 3.2 — تسجيل انتهاكات Rate Limit

| التفصيل | |
|---|---|
| **الموقع** | `utils/admin_decorator.py:107-113` |
| **المشكلة** | انتهاكات Rate Limit تحدث بصمت |

**الكود المُحسّن:**
```python
if not _check_rate_limit(user_id, func.__name__):
    logger.info(
        f"Rate limited: user_id={user_id}, "
        f"function={func.__name__}, "
        f"window={_get_rate_limit(func.__name__)}s"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer(
                text="⏳ يرجى الانتظار قليلاً",
                show_alert=False
            )
        except Exception:
            pass
    elif update.message:
        await update.message.reply_text("⏳ يرجى الانتظار قليلاً قبل إعادة المحاولة")
    return
```

---

### 3.3 — تحسين توقيت `update_activity()`

| التفصيل | |
|---|---|
| **الموقع** | `utils/admin_decorator.py:117` |
| **المشكلة** | `update_activity(user_id)` تُستدعى قبل تنفيذ الدالة |

**التحسين:** نقلها إلى بعد التنفيذ بنجاح:
```python
# كان (سطر 115-119):
from database.repositories.user_sessions import update_activity
update_activity(user_id)
return await func(update, context)

# يجب أن يكون:
result = await func(update, context)
from database.repositories.user_sessions import update_activity
update_activity(user_id)
return result
```

---

### 3.4 — تحويل `list.pop(0)` إلى `deque`

| التفصيل | |
|---|---|
| **الموقع** | ملف metrics (يجب التحقق من المسار الدقيق) |

**الكود الحالي (مفترض):**
```python
_requests = []
# ...
if len(_requests) > 1000:
    _requests.pop(0)  # O(n)
```

**الكود المُحسّن:**
```python
from collections import deque

_requests = deque(maxlen=1000)  # auto-evicts oldest — O(1)
```

---

### 3.5 — تنظيف ذاكرة المؤقتة بشكل دوري

| التفصيل | |
|---|---|
| **الموقع** | `core/profile_cache.py:36-38` |
| **المشكلة** | التنظيف يحدث فقط عند `get()` — العناصر البالية تبقى |

**الكود المُضاف:**
```python
def cleanup_stale(self) -> int:
    """حذف جميع العناصر البالية. يُعيد عدد العناصر المحذوفة."""
    with self._lock:
        now = time.time()
        stale_keys = [
            k for k, (ts, _) in self._store.items()
            if now - ts > self._ttl
        ]
        for k in stale_keys:
            del self._store[k]
        return len(stale_keys)
```

**تشغيل دوري (في `main.py` عبر JobQueue):**
```python
from core.profile_cache import profile_cache

async def cleanup_caches(context):
    removed = profile_cache.cleanup_stale()
    if removed:
        logger.info(f"Profile cache: cleaned {removed} stale entries")

# في post_init:
context.job_queue.run_repeating(cleanup_caches, interval=300, first=60)
```

---

## 4. المرحلة الثالثة: تحسينات متوسطة

> **المدة المقدرة:** 10-15 يوم
> **المخاطر:** متوسطة — تغييرات واسعة النطاق

---

### 4.1 — توحيد النصوص العربية المضمّنة

| التفصيل | |
|---|---|
| **العدد** | 73 ملف تحتوي نصوص عربية خارج `bot/messages.py` |
| **الأولوية** | الملفات الأكبر حجماً أولاً |

**خطوات التنفيذ:**
1. تحديد النصوص المكررة عبر:
   ```bash
   rg -n '[\u0600-\u06FF]+' --include '*.py' | grep -v bot/messages.py | head -50
   ```
2. نقل كل نص إلى `bot/messages.py` مع مفتاح واضح
3. تحديث handler لاستخدام المفتاح

**مثال:**
```python
# كان في handler:
await update.message.reply_text("❌ الحساب محظور")

# يجب أن يكون:
from bot.messages import ACCOUNT_BLOCKED_MSG
await update.message.reply_text(ACCOUNT_BLOCKED_MSG)
```

---

### 4.2 — توحيد `except Exception:`

| التفصيل | |
|---|---|
| **العدد** | 32 حالة `except Exception:` بدون ت绑 |

**النمط المطلوب:**
```python
# كان:
except Exception:
    pass

# يجب أن يكون:
except Exception as e:
    logger.debug(f"Expected error in {func.__name__}: {e}", exc_info=True)
```

---

### 4.3 — تقسيم `God Objects`

| الملف | الأسطر | الحل المقترح |
|---|---|---|
| `core/hotspot_manager.py` | 435 | تم استخراج `hotspot_blocking.py` — التكملة: `hotspot_expiry.py` + `hotspot_search_ops.py` |
| `core/userman_manager.py` | 487 | تقسيم: `userman_crud.py` + `userman_cards.py` + `userman_profiles.py` |

---

### 4.4 — تحسين LRU Eviction

| التفصيل | |
|---|---|
| **الموقع** | `core/profile_cache.py:46` |
| **المشكلة** | `min(self._store, key=...)` — O(n) لكل إخلاء |

**الكود المُحسّن:**
```python
from collections import OrderedDict

class ProfileCache:
    def __init__(self, ttl: int = PROFILE_CACHE_TTL_SECONDS, max_size: int = 200):
        self._ttl = ttl
        self._max_size = max_size
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, list[str]]] = OrderedDict()

    def get(self, router_key: str) -> list[str] | None:
        with self._lock:
            entry = self._store.get(router_key)
            if entry is None:
                return None
            ts, names = entry
            if time.time() - ts > self._ttl:
                del self._store[router_key]
                return None
            self._store.move_to_end(router_key)  # O(1)
            return list(names)

    def set(self, router_key: str, names: list[str]) -> None:
        with self._lock:
            if router_key in self._store:
                self._store.move_to_end(router_key)
            elif len(self._store) >= self._max_size:
                self._store.popitem(last=False)  # O(1) — remove oldest
            self._store[router_key] = (time.time(), list(names))
```

---

## 5. المرحلة الرابعة: تنظيف وتوثيق

> **المدة المقدرة:** مستمر (أثناء العمل على المراحل السابقة)

| # | المهمة | الجهد | الملفات |
|---|---|---|---|
| 5.1 | استخدام `TYPE_CHECKING` بدلاً من الاستيرادات الكسولة | منخفض | أي ملف يستخدم `if TYPE_CHECKING` |
| 5.2 | تنظيف `dead code` في `hotspot_search.py` | منخفض | `bot/handlers/hotspot_search.py` |
| 5.3 | تحديث `docs/evaluation_report.md` بعد كل مرحلة | منخفض | `docs/evaluation_report.md` |
| 5.4 | تقسيم `bot/messages.py` حسب المجال | متوسط | `bot/messages.py` → `bot/messages/` |
| 5.5 | إضافة اختبارات تغطية للتحسينات الجديدة | متوسط | `tests/` |

---

## 6. جدول الأولوية النهائي

### حسب المرحلة

| المرحلة | # | المهمة | التأثير | الجهد | المخاطر |
|---|---|---|---|---|---|
| 🔴 1 | 2.1 | validate_mac bug | **حرج** | 1 يوم | منخفض |
| 🔴 1 | 2.2 | uptime comparison | **حرج** | 1 يوم | منخفض |
| 🔴 1 | 2.3 | time.sleep blocking | **حرج** | 2 يوم | متوسط |
| 🔴 1 | 2.4 | classify_error timeout | **عالي** | 1 يوم | منخفض |
| 🟠 2 | 3.1 | Rate limit per-command | **عالي** | 2 يوم | منخفض |
| 🟠 2 | 3.2 | Rate limit logging | **متوسط** | نصف يوم | منخفض |
| 🟠 2 | 3.3 | update_activity timing | **متوسط** | 1 يوم | منخفض |
| 🟠 2 | 3.4 | list.pop → deque | **متوسط** | نصف يوم | منخفض |
| 🟠 2 | 3.5 | Cache periodic cleanup | **متوسط** | 1 يوم | منخفض |
| 🟡 3 | 4.1 | Arabic strings consolidation | **متوسط** | 5 أيام | متوسط |
| 🟡 3 | 4.2 | except Exception binding | **منخفض** | 3 أيام | منخفض |
| 🟡 3 | 4.3 | God Objects split | **متوسط** | 5 أيام | متوسط |
| 🟡 3 | 4.4 | LRU O(1) eviction | **منخفض** | 1 يوم | منخفض |
| 🟢 4 | 5.1-5.5 | تنظيف وتوثيق | **منخفض** | مستمر | منخفض |

---

### حسب التأثير

| التأثير | المهام | الإجمالي |
|---|---|---|
| **حرج** | 2.1, 2.2 | 2 يوم |
| **عالي** | 2.3, 2.4, 3.1 | 5 أيام |
| **متوسط** | 3.2, 3.3, 3.4, 3.5, 4.1, 4.3 | 10 أيام |
| **منخفض** | 4.2, 4.4, 5.1-5.5 | 4 أيام + مستمر |

---

## 7. مراجع التحليل

### الملفات المصدرة

| الملف | الغرض |
|---|---|
| `docs/evaluation_report.md` | التقرير الشامل للتقييم (v2.0) |
| `docs/priority-plan.md` | خطة الأولويات الأصلية |
| `docs/improvement_guide.md` | هذا الملف |

### الملفات المحللة

| الملف | النقاط المدروسة |
|---|---|
| `utils/admin_decorator.py` | Rate limit, update_activity, role checking |
| `utils/error_response.py` | classify_error, send_error, sanitization |
| `utils/validators.py` | validate_mac return type |
| `core/connection_pool.py` | time.sleep, retry logic, connection management |
| `core/hotspot_blocking.py` | validate_mac usage |
| `core/hotspot_manager.py` | uptime comparison, God Object |
| `core/profile_cache.py` | LRU eviction, cleanup |
| `core/mikrotik_api.py` | time.sleep in _throttle |

### أوامر التحقق

```bash
# بعد كل تغيير:
ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs
py -3.12 scripts/validate_handlers.py
py -3.12 -m pytest -q
```

---

## ملاحظات

- تم إعداد هذا الدليل بتاريخ 2026-07-22
- جميع التحسينات مبنية على تحليل مباشر للكود المصدري
- يُنصح بتنفيذ المراحل بالترتيب للحد من المخاطر
- يجب تحديث هذا الملف بعد تنفيذ كل مرحلة
