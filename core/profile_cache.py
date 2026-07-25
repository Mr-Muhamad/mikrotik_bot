"""In-memory TTL cache for MikroTik profile names.

يقلل عدد طلبات API المتكررة لجلب البروفايلات.
"""

import logging
import threading
import time
from collections import OrderedDict

from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

# عمر الكاش: 5 دقائق
PROFILE_CACHE_TTL_SECONDS = 5 * 60


class ProfileCache:
    """كاش بسيط مع TTL لمعلومات البروفايلات لكل راوتر.

    thread-safe للاستخدام من executors المتعددة.
    """

    def __init__(self, ttl: int = PROFILE_CACHE_TTL_SECONDS, max_size: int = 200) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, list[str]]] = OrderedDict()

    def get(self, router_key: str) -> list[str] | None:
        """جلب البروفايلات من الكاش. يُرجع None عند انتهاء الصلاحية أو عدم وجود."""
        with self._lock:
            entry = self._store.get(router_key)
            if entry is None:
                return None
            ts, names = entry
            if time.time() - ts > self._ttl:
                # تنظيف دوري
                self._store.pop(router_key, None)
                return None
            self._store.move_to_end(router_key)
            return list(names)  # نسخة للحماية من التعديل

    def set(self, router_key: str, names: list[str]) -> None:
        """تخزين البروفايلات في الكاش."""
        with self._lock:
            if router_key in self._store:
                self._store.move_to_end(router_key)
            elif len(self._store) >= self._max_size:
                self._store.popitem(last=False)
            self._store[router_key] = (time.time(), list(names))

    def invalidate(self, router_key: str) -> None:
        """حذف البروفايلات لراوتر محدد (مثلاً بعد edit profile)."""
        with self._lock:
            self._store.pop(router_key, None)

    def clear(self) -> None:
        """مسح الكاش بالكامل."""
        with self._lock:
            self._store.clear()

    def stats(self) -> RouterOSRow:
        """إحصائيات الكاش للمراقبة."""
        with self._lock:
            now = time.time()
            fresh = sum(1 for ts, _ in self._store.values() if now - ts <= self._ttl)
            return {
                "size": len(self._store),
                "fresh": fresh,
                "stale": len(self._store) - fresh,
                "ttl_seconds": self._ttl,
            }


profile_cache = ProfileCache()
