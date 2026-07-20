"""Router subsystem detection wrapper (Hotspot vs User Manager vs both).

Thin presentation layer over ``core.router_info``: delegates probe/cache
logic to the core layer and maps plain tokens (``"hotspot"``, ``"userman"``,
``"both"``, ``"unknown"``) to user-facing Arabic strings from ``bot.messages``.
"""

from bot.messages import (
    ROUTER_SYSTEM_BOTH,
    ROUTER_SYSTEM_HOTSPOT,
    ROUTER_SYSTEM_UNKNOWN,
    ROUTER_SYSTEM_USERMAN,
)
from core.router_info import (
    SYSTEM_BOTH,
    SYSTEM_HOTSPOT,
    SYSTEM_UNKNOWN,
    SYSTEM_USERMAN,
    detect_router_system,
)
from utils.async_blocking import run_blocking

# Map plain tokens -> user-facing Arabic strings.
_TOKEN_TO_TEXT = {
    SYSTEM_BOTH: ROUTER_SYSTEM_BOTH,
    SYSTEM_HOTSPOT: ROUTER_SYSTEM_HOTSPOT,
    SYSTEM_USERMAN: ROUTER_SYSTEM_USERMAN,
    SYSTEM_UNKNOWN: ROUTER_SYSTEM_UNKNOWN,
}


async def get_router_system_part(router_key: str | None) -> str:
    """Detect which user-management subsystem is active on the router.

    Returns one of ROUTER_SYSTEM_* Arabic constants from bot.messages.
    """
    token = await run_blocking(detect_router_system, router_key)
    return _TOKEN_TO_TEXT.get(token, ROUTER_SYSTEM_UNKNOWN)
