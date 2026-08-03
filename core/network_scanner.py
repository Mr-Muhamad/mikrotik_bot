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

from core.mikrotik_client import RouterOSRow
from core.network_probe import DiscoveredRouter, MNDPListenerProbe
from utils.async_blocking import run_blocking

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
    mndp_results: list[RouterOSRow] = []
    try:
        mndp_probe = MNDPListenerProbe(timeout=mndp_timeout)
        mndp_results = await mndp_probe.discover()
        logger.info("MNDP found %d devices", len(mndp_results))
    except PermissionError:
        logger.warning("MNDP requires Administrator privileges, falling back to ARP/Port scan")
    except OSError as e:
        logger.warning("MNDP discovery error: %s", e)

    # 2. ARP Table Probe (sync subprocess call — must not block the event loop)
    arp_results: list[RouterOSRow] = []
    try:
        arp_probe = ARPTableProbe()
        arp_results = await run_blocking(arp_probe.discover)
        logger.info("ARP probe found %d dynamic entries", len(arp_results))
    except OSError as e:
        logger.warning("ARP probe error: %s", e)

    # 3. Port Scan Probe on candidate IPs from ARP
    port_results: list[RouterOSRow] = []
    candidate_ips = [str(r["ip"]) for r in arp_results if r.get("ip")]
    if candidate_ips:
        try:
            port_probe = PortScanProbe(ips=candidate_ips, port=8728, timeout=1.5)
            port_results = await port_probe.discover()
            logger.info("Port scan found %d reachable API ports", len(port_results))
        except OSError as e:
            logger.warning("Port scan error: %s", e)

    # Merge results from all probes
    routers = merge_probe_results(arp_results, port_results, mndp_results)

    if progress_callback:
        await progress_callback(f"تم العثور على {len(routers)} روتر MikroTik على الشبكة")

    logger.info("Multi-strategy discovery finished: %d routers found", len(routers))
    return routers
