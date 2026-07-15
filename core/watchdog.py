import logging
import threading
from datetime import datetime
from librouteros.exceptions import LibRouterosError
from core.mikrotik_api import mikrotik_api
from core.stats import stats_manager

logger = logging.getLogger(__name__)

# الحالة المخزنة لكل راوتر: {router_key: {"last_ok": datetime, "last_fail": datetime, "alert_sent": bool}}
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
    """Check if a router is reachable. Returns status dict."""
    try:
        mikrotik_api.execute(router_key, "system/resource/print")
        with _router_status_lock:
            _router_status.setdefault(router_key, {})
            _router_status[router_key]["last_ok"] = datetime.now()
            _router_status[router_key]["alert_sent"] = False
        return {"online": True, "error": None}
    except (LibRouterosError, ConnectionError, OSError) as e:
        with _router_status_lock:
            _router_status.setdefault(router_key, {})
            _router_status[router_key]["last_fail"] = datetime.now()
        return {"online": False, "error": str(e)}


def get_router_status(router_key: str) -> dict:
    """Get cached status for a router."""
    with _router_status_lock:
        return dict(_router_status.get(router_key, {}))


def get_router_status_detail(router_key: str) -> dict:
    """Return enriched cached status with best-effort version and active users.

    The online determination relies only on cached health results, so this
    function never performs a fresh connectivity probe. Live data (RouterOS
    version, active Hotspot users) is fetched only when the router is considered
    online, and failures are swallowed so a partial outage never breaks the board.
    """
    with _router_status_lock:
        status = dict(_router_status.get(router_key, {}))
    last_ok = status.get("last_ok")
    last_fail = status.get("last_fail")
    online = bool(last_ok and (not last_fail or last_ok > last_fail))
    status["online"] = online
    status["version"] = None
    status["active_users"] = None
    if online:
        try:
            version = mikrotik_api.get_version(router_key)
            status["version"] = version if version and version != "unknown" else None
        except Exception:
            status["version"] = None
        try:
            hotspot_stats = stats_manager.get_hotspot_stats(router_key)
            status["active_users"] = (
                hotspot_stats.get("active_users") if hotspot_stats else None
            )
        except Exception:
            status["active_users"] = None
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
