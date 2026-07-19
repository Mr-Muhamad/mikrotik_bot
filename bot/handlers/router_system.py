"""Router subsystem detection (Hotspot vs User Manager vs both).

Extracted from ``bot.handlers.common`` so that the probe/cache logic for
detecting which user-management subsystem is active on a router stays
separate from Telegram handler concerns.

Hotspot and User Manager are SEPARATE RouterOS subsystems with different
APIs and data stores. We probe both quickly and cache the result in a
module-level dict to avoid repeated network calls on every menu render.
"""

import logging

from telegram.ext import ContextTypes

from core.mikrotik_api import mikrotik_api
from utils.async_blocking import run_blocking
from bot.messages import (
    ROUTER_SYSTEM_BOTH,
    ROUTER_SYSTEM_HOTSPOT,
    ROUTER_SYSTEM_USERMAN,
    ROUTER_SYSTEM_UNKNOWN,
)

logger = logging.getLogger(__name__)

_router_system_cache: dict[str, str] = {}


def context_user_data_get(router_key: str) -> str | None:
    """Best-effort read of cached router system type from module-level cache."""
    return _router_system_cache.get(router_key)


def context_user_data_set(router_key: str, value: str) -> None:
    """Store the detected router system type in the module-level cache."""
    _router_system_cache[router_key] = value


def _probe_path(router_key: str, path: str) -> bool:
    """Return True if the given API path is reachable (empty list counts as present)."""
    try:
        mikrotik_api.execute(router_key, path)
        return True
    except Exception:
        return False


async def get_router_system_part(router_key: str | None) -> str:
    """Detect which user-management subsystem is active on the router.

    Returns one of ROUTER_SYSTEM_* constants.
    """
    if not router_key:
        return ROUTER_SYSTEM_UNKNOWN
    cached = context_user_data_get(router_key)
    if cached:
        return cached
    try:
        is_healthy, _ = await run_blocking(
            mikrotik_api.check_connection_health, router_key
        )
        if not is_healthy:
            return ROUTER_SYSTEM_UNKNOWN

        has_hotspot = await run_blocking(
            _probe_path, router_key, "ip/hotspot/user/print"
        )
        um_base = mikrotik_api.get_userman_base_path(router_key)
        has_userman = await run_blocking(
            _probe_path, router_key, f"{um_base}/user/print"
        )
        if has_hotspot and has_userman:
            result = ROUTER_SYSTEM_BOTH
        elif has_hotspot:
            result = ROUTER_SYSTEM_HOTSPOT
        elif has_userman:
            result = ROUTER_SYSTEM_USERMAN
        else:
            result = ROUTER_SYSTEM_UNKNOWN
        context_user_data_set(router_key, result)
        return result
    except Exception:
        return ROUTER_SYSTEM_UNKNOWN
