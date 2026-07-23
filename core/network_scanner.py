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
from collections.abc import Awaitable, Callable
from typing import Any

from core.network_probe import DiscoveredRouter, MNDPListenerProbe

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]


class MNDPPermissionError(PermissionError):
    """Raised when MNDP socket requires admin/root privileges."""


async def discover_routers(
    mndp_timeout: float = 8.0,
    progress_callback: ProgressCallback | None = None,
) -> list[DiscoveredRouter]:
    """Discover MikroTik routers using a multi-strategy probe: MNDP + ARP + Port Scan.

    Args:
        mndp_timeout: How long the MNDP listener waits for replies (seconds).
        progress_callback: Optional async callable for progress messages.

    Returns:
        A list of DiscoveredRouter objects for discovered MikroTik devices.
    """
    from core.network_probe import ARPTableProbe, PortScanProbe, merge_probe_results

    logger.info("Starting multi-strategy router discovery...")
    if progress_callback:
        await progress_callback("جاري البحث عن أجهزة MikroTik عبر الشبكة المحلية (MNDP + ARP)...")

    # 1. MNDP Discovery
    mndp_results: list[dict[str, Any]] = []
    try:
        mndp_probe = MNDPListenerProbe(timeout=mndp_timeout)
        mndp_results = await mndp_probe.discover()
        logger.info(f"MNDP found {len(mndp_results)} devices")
    except PermissionError:
        logger.warning("MNDP requires Administrator privileges, falling back to ARP/Port scan")
    except Exception as e:
        logger.warning(f"MNDP discovery error: {e}")

    # 2. ARP Table Probe
    arp_results: list[dict[str, Any]] = []
    try:
        arp_probe = ARPTableProbe()
        arp_results = arp_probe.discover()
        logger.info(f"ARP probe found {len(arp_results)} dynamic entries")
    except Exception as e:
        logger.warning(f"ARP probe error: {e}")

    # 3. Port Scan Probe on candidate IPs from ARP
    port_results: list[dict[str, Any]] = []
    candidate_ips = [r["ip"] for r in arp_results if r.get("ip")]
    if candidate_ips:
        try:
            port_probe = PortScanProbe(ips=candidate_ips, port=8728, timeout=1.5)
            port_results = await port_probe.discover()
            logger.info(f"Port scan found {len(port_results)} reachable API ports")
        except Exception as e:
            logger.warning(f"Port scan error: {e}")

    # Merge results from all probes
    routers = merge_probe_results(arp_results, port_results, mndp_results)

    if progress_callback:
        await progress_callback(f"تم العثور على {len(routers)} روتر MikroTik على الشبكة")

    logger.info(f"Multi-strategy discovery finished: {len(routers)} routers found")
    return routers

