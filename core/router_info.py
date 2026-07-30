"""Router subsystem detection (Hotspot vs User Manager vs both).

Pure network/probe layer: no dependency on ``telegram`` or ``bot.*``.
Returns plain string tokens (``"hotspot"``, ``"userman"``, ``"both"``,
``"unknown"``) that the caller can map to user-facing constants.

Hotspot and User Manager are SEPARATE RouterOS subsystems with different
APIs and data stores. We probe both quickly and cache the result in a
module-level dict to avoid repeated network calls on every menu render.
"""

import logging

from librouteros.exceptions import TrapError

from core.mikrotik_api import mikrotik_api
from utils.formatters import sanitize_log_data

logger = logging.getLogger(__name__)

# Plain tokens (not user-facing strings).
SYSTEM_HOTSPOT = "hotspot"
SYSTEM_USERMAN = "userman"
SYSTEM_BOTH = "both"
SYSTEM_UNKNOWN = "unknown"

_router_system_cache: dict[str, str] = {}


def cache_get(router_key: str) -> str | None:
    """Best-effort read of cached router system type from module-level cache."""
    return _router_system_cache.get(router_key)


def cache_set(router_key: str, value: str) -> None:
    """Store the detected router system type in the module-level cache."""
    _router_system_cache[router_key] = value


def _probe_path(router_key: str, path: str) -> bool:
    """Return True if the given API path is reachable (empty list counts as present)."""
    try:
        mikrotik_api.execute(router_key, path)
        return True
    except (TrapError, ConnectionError, OSError) as e:
        logger.debug(
            "Probe failed for %s on %s (error type: %s): %s",
            path, router_key, type(e).__name__, sanitize_log_data(str(e)),
        )
        return False
    except Exception as e:  # noqa: BLE001
        logger.debug(
            "Probe failed for %s on %s (error type: %s): %s",
            path, router_key, type(e).__name__, sanitize_log_data(str(e)),
        )
        return False


def detect_router_system(router_key: str | None) -> str:
    """Detect which user-management subsystem is active on the router.

    Synchronous: caller is responsible for wrapping in ``run_blocking``.
    Returns one of the ``SYSTEM_*`` plain tokens defined in this module.
    """
    if not router_key:
        return SYSTEM_UNKNOWN
    cached = cache_get(router_key)
    if cached:
        return cached
    try:
        is_healthy, _ = mikrotik_api.check_connection_health(router_key)
        if not is_healthy:
            return SYSTEM_UNKNOWN

        has_hotspot = _probe_path(router_key, "ip/hotspot/user/print")
        um_base = mikrotik_api.get_userman_base_path(router_key)
        has_userman = _probe_path(router_key, f"{um_base}/user/print")
        if has_hotspot and has_userman:
            result = SYSTEM_BOTH
        elif has_hotspot:
            result = SYSTEM_HOTSPOT
        elif has_userman:
            result = SYSTEM_USERMAN
        else:
            result = SYSTEM_UNKNOWN
        cache_set(router_key, result)
        return result
    except (TrapError, ConnectionError, OSError) as e:
        logger.warning(
            "detect_router_system failed for %s (error type: %s): %s",
            router_key, type(e).__name__, sanitize_log_data(str(e)),
        )
        return SYSTEM_UNKNOWN
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "detect_router_system failed for %s (error type: %s): %s",
            router_key, type(e).__name__, sanitize_log_data(str(e)),
        )
        return SYSTEM_UNKNOWN
