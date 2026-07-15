"""Router discovery orchestrator using MNDP (MikroTik Neighbor Discovery Protocol).

MNDP is MikroTik's proprietary discovery protocol that broadcasts on UDP port 5678.
This module discovers MikroTik routers on the local network using MNDP.

MNDP behavior mirrors WinBox:
- Single socket for both send and receive (avoids race condition).
- Multiple refresh broadcasts during the listen window.
- Self-echo filtering (ignore our own broadcast replies).

Requirements:
- Admin/root privileges on Windows (raw UDP socket access).
- Port 5678/UDP must be open.
- Works only on local network (LAN, Layer 2 broadcast domain).
"""

import logging
from datetime import datetime
from typing import Awaitable, Callable

from core.network_probe import DiscoveredRouter, MNDPListenerProbe

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]


class MNDPPermissionError(PermissionError):
    """Raised when MNDP socket requires admin/root privileges."""


async def discover_routers(
    mndp_timeout: float = 10,
    progress_callback: ProgressCallback | None = None,
) -> list[DiscoveredRouter]:
    """Discover MikroTik routers using MNDP protocol.

    MNDP (MikroTik Neighbor Discovery Protocol) is MikroTik's proprietary
    protocol for discovering MikroTik devices on the local network.

    Args:
        mndp_timeout: How long the MNDP listener waits for replies (seconds).
        progress_callback: Optional async callable for progress messages.

    Returns:
        A list of DiscoveredRouter objects for discovered MikroTik devices.

    Raises:
        MNDPPermissionError: If the OS denies raw UDP socket access (Windows
            requires running as Administrator).
    """
    logger.info("Starting MNDP router discovery...")
    if progress_callback:
        await progress_callback("جاري بحث MNDP عن أجهزة MikroTik...")

    mndp_probe = MNDPListenerProbe(timeout=mndp_timeout)
    mndp_results = await mndp_probe.discover()
    logger.info(f"MNDP found {len(mndp_results)} MikroTik devices")

    # Convert MNDP results to DiscoveredRouter objects
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    routers = []
    for entry in mndp_results:
        router = DiscoveredRouter(
            ip_address=entry.get("ipv4") or entry.get("ip", ""),
            mac_address=entry.get("mac", ""),
            identity=entry.get("identity", "Unknown"),
            version=entry.get("version", ""),
            board=entry.get("board", ""),
            software_id=entry.get("software_id", ""),
            platform=entry.get("platform", "MikroTik"),
            uptime=entry.get("uptime", ""),
            interface_name=entry.get("interface_name", ""),
            source="mndp",
            last_seen=entry.get("last_seen", now),
        )
        routers.append(router)

    if progress_callback:
        await progress_callback(f"تم العثور على {len(routers)} روتر MikroTik")

    logger.info(f"MNDP discovered: {len(routers)} MikroTik routers")
    return routers
