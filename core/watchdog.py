import logging
import threading
from datetime import datetime

from librouteros.exceptions import LibRouterosError

from core.mikrotik_api import mikrotik_api
from core.stats import stats_manager
from database.repositories.router_health import get_all_latest_health, record_health

logger = logging.getLogger(__name__)

# الحالة المخزنة لكل راوتر: {router_key: {"last_ok": datetime, "last_fail": datetime, "alert_sent": bool}}  # noqa: E501
_router_status: dict[str, dict] = {}
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


def check_router_health(router_key: str) -> dict:
    """Check if a router is reachable and monitor CPU/memory thresholds. Returns status dict."""
    try:
        res = mikrotik_api.execute(router_key, "system/resource/print")
        cpu_load = None
        free_mem = None
        if res and isinstance(res, list) and len(res) > 0:
            info = res[0]
            try:
                cpu_load = int(info.get("cpu-load", 0))
                free_mem = int(info.get("free-memory", 0))
            except (ValueError, TypeError):
                pass

        with _router_status_lock:
            _router_status.setdefault(router_key, {})
            _router_status[router_key]["last_ok"] = datetime.now()
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
        except Exception:
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
            _router_status[router_key]["last_fail"] = datetime.now()
        record_health(router_key, "offline", str(e))
        return {"online": False, "error": str(e)}


def get_router_status(router_key: str) -> dict:
    """Get cached status for a router."""
    with _router_status_lock:
        return dict(_router_status.get(router_key, {}))


def get_router_status_detail(router_key: str) -> dict:
    """Return enriched cached status with best-effort version and active users.

    Hybrid Check (Option 2): If the router has an active connection in the pool,
    it is immediately considered online regardless of the cache. Otherwise, falls
    back to cache. Live data (version, users) is fetched only when online.
    """
    has_active = mikrotik_api.has_active_connection(router_key)

    with _router_status_lock:
        status = dict(_router_status.get(router_key, {}))

    last_ok = status.get("last_ok")
    last_fail = status.get("last_fail")

    if has_active:
        online = True
        if not last_ok or (last_fail and last_fail >= last_ok):
            status["last_ok"] = datetime.now()
    else:
        online = bool(last_ok and (not last_fail or last_ok > last_fail))

    status["online"] = online
    status["version"] = None
    status["active_users"] = None

    if has_active:
        try:
            version = mikrotik_api.get_version(router_key)
            status["version"] = version if version and version != "unknown" else None
        except Exception:
            status["version"] = None
        try:
            hotspot_stats = stats_manager.get_hotspot_stats(router_key)
            status["active_users"] = hotspot_stats.get("active_users") if hotspot_stats else None
        except Exception:
            status["active_users"] = None
    else:
        # إذا لم يكن هناك اتصال نشط، نكتفي بالإصدار المكيّش إن وُجد ولا نحاول جلب الإحصائيات الحية
        # لتجنب تجميد البوت لمدة 90 ثانية إذا كان الراوتر غير متصل فعلياً.
        version = mikrotik_api.get_cached_version(router_key)
        status["version"] = version if version and version != "unknown" else None

    return status


def was_alert_sent(router_key: str) -> bool:
    """Check if an alert was already sent for current outage."""
    with _router_status_lock:
        return _router_status.get(router_key, {}).get("alert_sent", False)


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
    try:
        all_latest = get_all_latest_health()
        with _router_status_lock:
            for router_key, row in all_latest.items():
                is_online = row["status"] == "online"
                checked_at_str = row.get("checked_at", "")
                # تحويل النص إلى datetime للتوافق مع get_router_status_detail
                try:
                    from datetime import datetime as _dt

                    checked_at = _dt.strptime(checked_at_str, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    checked_at = None
                _last_known_status[router_key] = is_online
                _router_status.setdefault(router_key, {})
                if is_online and checked_at:
                    _router_status[router_key]["last_ok"] = checked_at
                elif not is_online and checked_at:
                    _router_status[router_key]["last_fail"] = checked_at
                # alert_sent يبدأ دائماً كـ False بعد restart لضمان إرسال تنبيه جديد إذا ظل offline
                _router_status[router_key].setdefault("alert_sent", False)
        logger.info(f"Watchdog: loaded status for {len(all_latest)} routers from DB")
    except Exception as e:
        logger.warning(f"Watchdog: failed to load status from DB: {e}")
