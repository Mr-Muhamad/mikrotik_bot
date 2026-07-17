import threading
import time
from collections import OrderedDict

_CACHE_TTL = 3600           # صلاحية الكاش لمدة ساعة كافتراضي
_MAX_CACHE_SIZE = 100       # الحد الأقصى لعناصر الكاش

class TTLCache:
    """Cache مع صلاحية محددة (TTL) لتخزين البيانات المؤقتة."""
    def __init__(self, max_size: int = _MAX_CACHE_SIZE, ttl: int = _CACHE_TTL):
        self._cache: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._cache_lock = threading.Lock()

    def get(self, key: str) -> object | None:
        with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self._cache.move_to_end(key)
                    return value
                else:
                    del self._cache[key]
            return None

    def set(self, key: str, value: object):
        with self._cache_lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.time())

    def invalidate(self, key: str):
        with self._cache_lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._cache_lock:
            self._cache.clear()

    def get_keys(self) -> list[str]:
        """إرجاع قائمة بالمفاتيح الحالية في الكاش (لأغراض المراقبة)."""
        with self._cache_lock:
            now = time.time()
            return [k for k, v in self._cache.items() if now - v[1] < self._ttl]

    def __len__(self) -> int:
        with self._cache_lock:
            now = time.time()
            return len([k for k, v in self._cache.items() if now - v[1] < self._ttl])

