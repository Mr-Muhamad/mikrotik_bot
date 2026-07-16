import logging
import time
import threading
from collections import OrderedDict

from librouteros import connect
from librouteros.exceptions import LibRouterosError

from database.models import get_router_by_id
from config import ROUTER_KEY_PREFIX
from core.exceptions import RouterNotFoundError

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 1
CONNECT_TIMEOUT = 10       # مهلة إنشاء الاتصال بالثواني
API_TIMEOUT = 30            # مهلة عامة لأوامر API (قراءة وكتابة)
LONG_TIMEOUT = 120          # مهلة للعمليات الطويلة (باكوب، جلب 1000+ مستخدم)
MAX_CONNECTIONS = 20        # الحد الأقصى لعدد الاتصالات المتزامنة

# إعدادات Cache
_CACHE_TTL = 3600           # صلاحية الكاش لمدة ساعة
_MAX_CACHE_SIZE = 100       # الحد الأقصى لعناصر الكاش


class TTLCache:
    """Cache مع صلاحية محددة (TTL) لتخزين البيانات المؤقتة.

    Thread-safe: كل عملية قراءة/كتابة/حذف محمية بـ _cache_lock منفصل عن
    قفل ConnectionPool حتى لا يحدث deadlock عند الاستخدام المتداخل.
    """

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

    def __contains__(self, key: str) -> bool:
        with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return True
                del self._cache[key]
            return False

    def __len__(self) -> int:
        with self._cache_lock:
            self._evict_expired_unsafe()
            return len(self._cache)

    def _evict_expired_unsafe(self):
        """طرد العناصر المنتهية — يُستدعى فقط من داخل _cache_lock."""
        now = time.time()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts >= self._ttl]
        for k in expired:
            del self._cache[k]

    def _evict_expired(self):
        """طرد العناصر المنتهية — واجهة آمنة لـ thread خارج الكلاس."""
        with self._cache_lock:
            self._evict_expired_unsafe()

    def __eq__(self, other) -> bool:
        if isinstance(other, dict):
            self._evict_expired()
            with self._cache_lock:
                return {k: v for k, (v, _) in self._cache.items()} == other
        return NotImplemented


class ConnectionPool:
    """Manages MikroTik RouterOS API connections with pooling, retry, and cleanup."""

    def __init__(self):
        # RLock يسمح لنفس الـ thread بأخذ القفل عدة مرات (recursive).
        # مفيد في retry path حيث نحتاج lock داخل lock.
        self._lock = threading.RLock()
        self.connections: dict[str, object] = {}
        self.connection_times: dict[str, float] = {}
        self._last_used: dict[str, float] = {}
        self.router_versions = TTLCache(max_size=50, ttl=86400)  # 24 ساعة
        self.router_names = TTLCache(max_size=50, ttl=86400)     # 24 ساعة
        self._last_cleanup = 0.0
        self._cleanup_interval = 300
        self._max_connection_age = 3600
        self._idle_timeout = 600  # إعادة الاتصال بعد 10 دقائق خمول
        self.total_connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.cache_hits = 0

    def get_router_info(self, router_key: str) -> dict:
        if router_key.startswith(ROUTER_KEY_PREFIX):
            db_id = router_key.replace(ROUTER_KEY_PREFIX, "")
            router_cfg = get_router_by_id(int(db_id))
            if not router_cfg:
                raise RouterNotFoundError(f"Discovered router #{db_id} not found in database")
            return {
                "host": router_cfg["ip_address"],
                "port": router_cfg["port"],
                "user": router_cfg["username"],
                "password": router_cfg["password"],
                "name": router_cfg.get("identity", router_cfg["ip_address"]),
            }
        raise RouterNotFoundError(
            f"Router '{router_key}' not configured. Please discover and select a router first."
        )

    def _connect(self, router_info: dict, timeout: int | None = None) -> object:
        timeout = timeout or CONNECT_TIMEOUT
        api = connect(
            username=router_info["user"],
            password=router_info["password"],
            host=router_info["host"],
            port=router_info["port"],
            encoding="utf-8",
            timeout=timeout,
        )
        return api

    def _connect_long_running(self, router_info: dict) -> object:
        return self._connect(router_info, timeout=LONG_TIMEOUT)

    def _connect_with_retry(self, router_info: dict, router_key: str, timeout: int | None = None) -> object:
        last_error = None
        for attempt in range(1 + MAX_RETRIES):
            with self._lock:
                self.total_connection_attempts += 1
            try:
                api = self._connect(router_info, timeout=timeout)
                now = time.time()
                with self._lock:
                    existing = self.connections.get(router_key)
                    if existing is not None and existing is not api:
                        try:
                            existing.close()
                        except OSError as e:
                            logger.debug(f"Error closing old connection for {router_key}: {e}")
                    self.connections[router_key] = api
                    self.connection_times[router_key] = now
                    self._last_used[router_key] = now
                    self.successful_connections += 1
                logger.info(f"Connected to {router_info['name']} (attempt {attempt + 1})")
                return api
            except LibRouterosError as e:
                with self._lock:
                    self.failed_connections += 1
                last_error = e
                logger.warning(
                    f"Connection attempt {attempt + 1}/{1 + MAX_RETRIES} "
                    f"failed for {router_info['name']}: {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        logger.error(
            f"Failed to connect to {router_info['name']} after {1 + MAX_RETRIES} attempts"
        )
        raise last_error

    def _get_or_create_connection(self, router_key: str, timeout: int | None) -> object:
        """Core connection retrieval: check idle timeout, evict LRU if full, then connect."""
        self._maybe_cleanup()
        idle_api = None
        evict_api = None
        with self._lock:
            if router_key in self.connections:
                now = time.time()
                idle_secs = now - self._last_used.get(router_key, now)
                if idle_secs <= self._idle_timeout:
                    self.cache_hits += 1
                    self._last_used[router_key] = now
                    return self.connections[router_key]
                logger.debug(f"Connection for {router_key} idle {idle_secs:.0f}s, reconnecting proactively")
                idle_api = self.connections.pop(router_key, None)
                self.connection_times.pop(router_key, None)
                self._last_used.pop(router_key, None)
            if len(self.connections) >= MAX_CONNECTIONS:
                lru_key = (
                    min(self._last_used, key=self._last_used.get)
                    if self._last_used
                    else min(self.connection_times, key=self.connection_times.get)
                )
                logger.info(f"Connection pool full ({MAX_CONNECTIONS}), evicting LRU: {lru_key}")
                evict_api = self.connections.pop(lru_key, None)
                self.connection_times.pop(lru_key, None)
                self._last_used.pop(lru_key, None)
                self.router_versions.invalidate(lru_key)
                self.router_names.invalidate(lru_key)
        for api_to_close in filter(None, [idle_api, evict_api]):
            try:
                api_to_close.close()
            except OSError as e:
                logger.debug(f"Error closing connection: {e}")
        router_info = self.get_router_info(router_key)
        return self._connect_with_retry(router_info, router_key, timeout=timeout)

    def get_connection(self, router_key: str = "router1") -> object:
        return self._get_or_create_connection(router_key, timeout=None)

    def get_long_connection(self, router_key: str = "router1") -> object:
        return self._get_or_create_connection(router_key, timeout=LONG_TIMEOUT)

    def _maybe_cleanup(self):
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        connections_to_close: list[tuple[str, object]] = []
        with self._lock:
            if now - self._last_cleanup < self._cleanup_interval:
                return
            self._last_cleanup = now
            stale_keys = [
                k
                for k, t in self.connection_times.items()
                if now - t > self._max_connection_age
            ]
            for key in stale_keys:
                logger.info(f"Cleaning up stale connection for {key}")
                api = self.connections.pop(key, None)
                self.connection_times.pop(key, None)
                self._last_used.pop(key, None)
                self.router_versions.invalidate(key)
                self.router_names.invalidate(key)
                if api:
                    connections_to_close.append((key, api))
        for key, api in connections_to_close:
            try:
                api.close()
            except OSError as e:
                logger.debug(f"Error closing stale connection for {key}: {e}")

    def reconnect(self, router_key: str, timeout: int | None = None) -> object:
        """Close and re-establish a connection for a given router key."""
        self.close_connection(router_key)
        self.router_versions.invalidate(router_key)
        router_info = self.get_router_info(router_key)
        return self._connect_with_retry(router_info, router_key, timeout=timeout)

    def replace_connection(self, router_key: str, new_api: object):
        """Replace an existing connection atomically."""
        now = time.time()
        with self._lock:
            existing = self.connections.get(router_key)
            if existing is not None and existing is not new_api:
                try:
                    existing.close()
                except OSError as e:
                    logger.debug(f"Error closing old connection for {router_key}: {e}")
            self.connections[router_key] = new_api
            self.connection_times[router_key] = now
            self._last_used[router_key] = now

    def close_connection(self, router_key: str):
        with self._lock:
            api = self.connections.pop(router_key, None)
            self.connection_times.pop(router_key, None)
            self._last_used.pop(router_key, None)
            self.router_versions.invalidate(router_key)
            self.router_names.invalidate(router_key)
        if api:
            try:
                api.close()
            except OSError as e:
                logger.debug(f"Error closing connection for {router_key}: {e}")

    def close_all(self):
        with self._lock:
            keys = list(self.connections.keys())
        for key in keys:
            self.close_connection(key)

    def get_version(self, router_key: str = "router1") -> str:
        with self._lock:
            cached = self.router_versions.get(router_key)
            return cached if cached else ""

    def set_version(self, router_key: str, version: str):
        with self._lock:
            self.router_versions.set(router_key, version)

    def get_cached_name(self, router_key: str) -> str | None:
        with self._lock:
            return self.router_names.get(router_key)

    def set_cached_name(self, router_key: str, name: str):
        with self._lock:
            self.router_names.set(router_key, name)

    def invalidate_name(self, router_key: str):
        with self._lock:
            self.router_names.invalidate(router_key)

    def invalidate_version(self, router_key: str):
        with self._lock:
            self.router_versions.invalidate(router_key)

    def get_metrics(self) -> dict:
        with self._lock:
            active = len(self.connections)
            stale = sum(
                1 for t in self.connection_times.values()
                if time.time() - t > self._max_connection_age
            )
            cached_names = len(self.router_names)
            cached_versions = len(self.router_versions)
        return {
            "active_connections": active,
            "stale_connections": stale,
            "total_attempts": self.total_connection_attempts,
            "successful": self.successful_connections,
            "failed": self.failed_connections,
            "cache_hits": self.cache_hits,
            "cached_names": cached_names,
            "cached_versions": cached_versions,
        }
