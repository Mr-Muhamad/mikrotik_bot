import logging
import threading
from datetime import datetime

from librouteros.exceptions import LibRouterosError

from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from core.stats import stats_manager
from database.repositories.router_health import get_all_latest_health, record_health
from utils.logging_setup import COMPONENT_SERVICE, bind_component

logger = logging.getLogger(__name__)

# الحالة المخزنة لكل راوتر: {router_key: {"last_ok": datetime, "last_fail": datetime, "alert_sent": bool}}  # noqa: E501
_router_status: dict[str, RouterOSRow] = {}
# آخر حالة معروفة (online/offline) لتحديد تغيّر الحالة وإرسال التنبيه مرة واحدة
_last_known_status: dict[str, bool] = {}
_router_status_lock = threading.Lock()

ALERT_NONE = "none"
ALERT_WENT_OFFLINE = "went_offline"
ALERT_RECOVERED = "recovered"


def record_check_result(router_key: str, is_online: bool) -> str:
    """Record a health check result. Returns the alert action to take (ALERT_* constant)."""
    with _router_status_lock:
        was_online = _last_known_status.get(router_key, True)
        _last_known_status[router_key] = is_online
        if not is_online and was_online:
            status = _router_status.get(router_key, {})
            if not status.get("alert_sent", False):
                _router_status.setdefault(router_key, {})["alert_sent"] = True
                return ALERT_WENT_OFFLINE
        elif is_online and not was_online:
            if router_key in _router_status:
                _router_status[router_key]["alert_sent"] = False
            return ALERT_RECOVERED
        return ALERT_NONE


def check_router_health(router_key: str) -> RouterOSRow:
    """Check if a router is reachable and monitor CPU/memory thresholds. Returns status dict."""
    with bind_component(COMPONENT_SERVICE):
        try:
            res = mikrotik_api.execute(router_key, "system/resource/print")
            cpu_load = None
            free_mem = None
            if res and len(res) > 0:
                info = res[0]
                try:
                    cpu_load = int(str(info.get("cpu-load", "0")))
                    free_mem = int(str(info.get("free-memory", "0")))
                except (ValueError, TypeError):
                    pass

            with _router_status_lock:
                _router_status.setdefault(router_key, {})
                _router_status[router_key]["last_ok"] = datetime.now().isoformat()
                _router_status[router_key]["alert_sent"] = False
                _router_status[router_key]["cpu_load"] = cpu_load
                _router_status[router_key]["free_memory"] = free_mem

            record_health(router_key, "online")

            # Upstream ISP Failover & Ping Monitor
            isp_ok = True
            latency_ms = None
            try:
                import socket
                import time

                start_time = time.monotonic()
                s = socket.create_connection(("8.8.8.8", 53), timeout=2.0)
                s.close()
                latency_ms = round((time.monotonic() - start_time) * 1000, 1)
            except OSError as ex:
                logger.debug(
                    "ISP ping check failed: %s", ex, extra={"component": COMPONENT_SERVICE}
                )
                isp_ok = False

            return {
                "online": True,
                "error": None,
                "cpu_load": cpu_load,
                "free_memory": free_mem,
                "isp_ok": isp_ok,
                "latency_ms": latency_ms,
            }
        except (LibRouterosError, ConnectionError, OSError) as e:
            with _router_status_lock:
                _router_status.setdefault(router_key, {})
                _router_status[router_key]["last_fail"] = datetime.now().isoformat()
            record_health(router_key, "offline", str(e))
            logger.warning(
                "Health check failed for %s: %s",
                router_key,
                e,
                extra={"component": COMPONENT_SERVICE},
            )
            return {"online": False, "error": str(e)}


def get_router_status(router_key: str) -> RouterOSRow:
    """Get cached status for a router."""
    with _router_status_lock:
        return dict(_router_status.get(router_key, {}))


def get_router_status_detail(router_key: str) -> RouterOSRow:
    """Return enriched cached status with best-effort version and active users.

    Hybrid Check (Option 2): If the router has an active connection in the pool,
    it is immediately considered online regardless of the cache. Otherwise, falls
    back to cache. Live data (version, users) is fetched only when online.
    """
    with bind_component(COMPONENT_SERVICE):
        has_active = mikrotik_api.has_active_connection(router_key)

        with _router_status_lock:
            status = dict(_router_status.get(router_key, {}))

        last_ok = status.get("last_ok")
        last_fail = status.get("last_fail")

        def _parse_dt(val: str | None) -> datetime | None:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        last_ok_dt = _parse_dt(last_ok) if isinstance(last_ok, str) else None
        last_fail_dt = _parse_dt(last_fail) if isinstance(last_fail, str) else None

        if has_active:
            online = True
            if not last_ok_dt or (last_fail_dt and last_fail_dt >= last_ok_dt):
                status["last_ok"] = datetime.now().isoformat()
        else:
            online = bool(last_ok_dt and (not last_fail_dt or last_ok_dt > last_fail_dt))

        status["online"] = online
        status["version"] = None
        status["active_users"] = None

        if has_active:
            try:
                version = mikrotik_api.get_version(router_key)
                status["version"] = version if version and version != "unknown" else None
            except (LibRouterosError, ConnectionError, OSError) as ex:
                logger.debug(
                    "Failed to fetch version in watchdog detail for %s: %s",
                    router_key,
                    ex,
                    extra={"component": COMPONENT_SERVICE},
                )
                status["version"] = None
            try:
                hotspot_stats = stats_manager.get_hotspot_stats(router_key)
                status["active_users"] = hotspot_stats.get("active_users") if hotspot_stats else None
            except (LibRouterosError, ConnectionError, OSError) as ex:
                logger.debug(
                    "Failed to fetch hotspot stats in watchdog detail for %s: %s",
                    router_key,
                    ex,
                    extra={"component": COMPONENT_SERVICE},
                )
                status["active_users"] = None
        else:
            version = mikrotik_api.get_cached_version(router_key)
            status["version"] = version if version and version != "unknown" else None

        return status


def was_alert_sent(router_key: str) -> bool:
    """Check if an alert was already sent for current outage."""
    with _router_status_lock:
        return bool(_router_status.get(router_key, {}).get("alert_sent", False))


def mark_alert_sent(router_key: str):
    """Mark that an alert has been sent for this router."""
    with _router_status_lock:
        if router_key in _router_status:
            _router_status[router_key]["alert_sent"] = True


def clear_alert_sent(router_key: str):
    """Reset alert flag so next offline triggers a new alert."""
    with _router_status_lock:
        if router_key in _router_status:
            _router_status[router_key]["alert_sent"] = False


def clear_status(router_key: str):
    """Clear status for a router (e.g. after deletion)."""
    with _router_status_lock:
        _router_status.pop(router_key, None)
        _last_known_status.pop(router_key, None)


def load_status_from_db() -> None:
    """تحميل آخر حالة معروفة لكل الراوترات من DB إلى الـ in-memory dicts.

    يُستدعى مرة واحدة عند startup (في post_init) لاستعادة الحالة بعد restart.
    """
    with bind_component(COMPONENT_SERVICE):
        try:
            all_latest = get_all_latest_health()
            with _router_status_lock:
                for router_key, row in all_latest.items():
                    is_online = row["status"] == "online"
                    checked_at_str = str(row.get("checked_at", ""))
                    # تحويل النص إلى datetime للتوافق مع get_router_status_detail
                    try:
                        from datetime import datetime as _dt

                        checked_at = _dt.strptime(checked_at_str, "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        checked_at = None
                    _last_known_status[router_key] = is_online
                    _router_status.setdefault(router_key, {})
                    if is_online and checked_at:
                        _router_status[router_key]["last_ok"] = checked_at.isoformat()
                    elif not is_online and checked_at:
                        _router_status[router_key]["last_fail"] = checked_at.isoformat()
                    # alert_sent يبدأ دائماً كـ False بعد restart لضمان إرسال تنبيه جديد إذا ظل offline
                    _router_status[router_key].setdefault("alert_sent", False)
            logger.info(
                "Watchdog: loaded status for %d routers from DB",
                len(all_latest),
            )
        except Exception as e:  # noqa: BLE001 - catch-all: log unexpected error before returning result
            logger.warning(
                "Watchdog: failed to load status from DB "
                "(error type: %s): %s",
                type(e).__name__,
                e,
                extra={"component": COMPONENT_SERVICE},
            exc_info=True,
            )
