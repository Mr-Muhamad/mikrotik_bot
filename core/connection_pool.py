import logging
import queue
import threading
import time

from librouteros import connect
from librouteros.api import Api
from librouteros.exceptions import LibRouterosError

from config import ROUTER_KEY_PREFIX
from core.cache import TTLCache
from core.exceptions import RouterNotFoundError
from database.models import get_router_by_id

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 1
CONNECT_TIMEOUT = 10  # مهلة إنشاء الاتصال بالثواني
API_TIMEOUT = 30  # مهلة عامة لأوامر API (قراءة وكتابة)
LONG_TIMEOUT = 120  # مهلة للعمليات الطويلة (باكوب، جلب 1000+ مستخدم)
MAX_CONNECTIONS_PER_ROUTER = 3  # عدد الاتصالات المسموح بها لكل راوتر معاً

# إعدادات Cache
_CACHE_TTL = 3600  # صلاحية الكاش لمدة ساعة
_MAX_CACHE_SIZE = 100  # الحد الأقصى لعناصر الكاش


class ConnectionPool:
    """Manages MikroTik RouterOS API connections with thread-safe queues per router."""

    def __init__(self):
        self._lock = threading.RLock()

        # Mapping router_key -> queue of IDLE Api objects
        self.pools: dict[str, queue.Queue[Api]] = {}
        # Mapping router_key -> total active + idle connections created
        self.active_counts: dict[str, int] = {}

        # Meta caches
        self.router_versions = TTLCache(max_size=50, ttl=86400)  # 24 ساعة
        self.router_names = TTLCache(max_size=50, ttl=86400)  # 24 ساعة

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

    def _connect(self, router_info: dict, timeout: int | None = None) -> Api:
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

    def _connect_with_retry(self, router_info: dict, timeout: int | None = None) -> Api:
        last_error: LibRouterosError | None = None
        for attempt in range(1 + MAX_RETRIES):
            with self._lock:
                self.total_connection_attempts += 1
            try:
                api = self._connect(router_info, timeout=timeout)
                with self._lock:
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
        logger.error(f"Failed to connect to {router_info['name']} after {1 + MAX_RETRIES} attempts")
        raise last_error  # type: ignore[misc]

    def get_connection(self, router_key: str = "router1", timeout: int | None = None) -> Api:
        """
        يحصل على اتصال جاهز من الطابور، أو ينشئ اتصالاً جديداً إذا لم يتجاوز الحد.
        إذا تجاوز الحد (MAX_CONNECTIONS_PER_ROUTER)، سينتظر حتى يفرغ اتصال من الطابور.
        """
        with self._lock:
            if router_key not in self.pools:
                self.pools[router_key] = queue.Queue(maxsize=MAX_CONNECTIONS_PER_ROUTER)
                self.active_counts[router_key] = 0

            q = self.pools[router_key]
            count = self.active_counts[router_key]

            if q.empty() and count < MAX_CONNECTIONS_PER_ROUTER:
                # لا يوجد اتصال فارغ ويمكننا إنشاء واحد جديد
                self.active_counts[router_key] += 1
                create_new = True
            else:
                # إما أن الطابور به اتصالات فارغة، أو وصلنا للحد الأقصى ويجب أن ننتظر
                create_new = False

        if create_new:
            try:
                router_info = self.get_router_info(router_key)
                api = self._connect_with_retry(router_info, timeout)
                return api
            except Exception:
                # إذا فشل إنشاء الاتصال، ننقص العداد
                with self._lock:
                    self.active_counts[router_key] -= 1
                raise
        else:
            try:
                # انتظار 30 ثانية كحد أقصى للحصول على اتصال فارغ (Throttle)
                api = q.get(timeout=30)
                with self._lock:
                    self.cache_hits += 1
                return api
            except queue.Empty:
                logger.error(
                    f"Connection pool timeout for {router_key}. Too many concurrent requests."
                )
                raise TimeoutError(
                    "Connection pool timeout: too many concurrent requests to the router"
                ) from None

    def release_connection(self, router_key: str, api: Api, broken: bool = False):
        """
        يجب مناداة هذه الدالة دائماً لإعادة الاتصال للطابور بعد الانتهاء.
        إذا كان broken=True، سيتم تدمير الاتصال وإنقاص العداد ليتم إنشاء غيره لاحقاً.
        """
        if broken:
            with self._lock:
                if self.active_counts.get(router_key, 0) > 0:
                    self.active_counts[router_key] -= 1
            try:
                api.close()
            except Exception as e:
                logger.debug(f"Error closing broken connection for {router_key}: {e}")
        else:
            with self._lock:
                if router_key in self.pools:
                    try:
                        self.pools[router_key].put_nowait(api)
                    except queue.Full:
                        # Should not happen unless logic is flawed
                        api.close()
                        self.active_counts[router_key] -= 1

    def reconnect(self, router_key: str, timeout: int | None = None) -> Api:
        """Close cache and establish a fresh connection."""
        self.router_versions.invalidate(router_key)
        self.router_names.invalidate(router_key)

        with self._lock:
            if router_key not in self.pools:
                self.pools[router_key] = queue.Queue(maxsize=MAX_CONNECTIONS_PER_ROUTER)
                self.active_counts[router_key] = 0

            # We are assuming this is used when a connection is marked broken
            # and we need a replacement immediately.
            self.active_counts[router_key] += 1

        try:
            router_info = self.get_router_info(router_key)
            return self._connect_with_retry(router_info, timeout)
        except Exception:
            with self._lock:
                self.active_counts[router_key] -= 1
            raise

    def close_connection(self, router_key: str):
        """Closes all idle connections for a specific router."""
        with self._lock:
            self.router_versions.invalidate(router_key)
            self.router_names.invalidate(router_key)
            q = self.pools.get(router_key)
            if not q:
                return

            # Empty the queue and close each
            while not q.empty():
                try:
                    api = q.get_nowait()
                    api.close()
                    self.active_counts[router_key] -= 1
                except (queue.Empty, Exception):
                    pass

    def close_all(self):
        with self._lock:
            keys = list(self.pools.keys())
        for key in keys:
            self.close_connection(key)

    def get_version(self, router_key: str = "router1") -> str:
        with self._lock:
            cached = self.router_versions.get(router_key)
            return str(cached) if cached else ""

    def set_version(self, router_key: str, version: str):
        with self._lock:
            self.router_versions.set(router_key, version)

    def get_cached_name(self, router_key: str) -> str | None:
        with self._lock:
            cached = self.router_names.get(router_key)
            return str(cached) if cached is not None else None

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
            active = sum(self.active_counts.values())
            idle = sum(q.qsize() for q in self.pools.values())
            cached_names = len(self.router_names)
            cached_versions = len(self.router_versions)
        return {
            "active_connections": active,
            "idle_connections": idle,
            "total_attempts": self.total_connection_attempts,
            "successful": self.successful_connections,
            "failed": self.failed_connections,
            "cache_hits": self.cache_hits,
            "cached_names": cached_names,
            "cached_versions": cached_versions,
        }

    def has_active_connection(self, router_key: str) -> bool:
        """Check if the router currently has any active or idle connections."""
        with self._lock:
            return self.active_counts.get(router_key, 0) > 0
