"""Hotspot host/user search and kick operations.

Extracted from ``core.hotspot_manager`` so that user-lifecycle CRUD stays
separate from host discovery and active-session eviction. These functions
are pure with respect to the MikroTik API client: they take an API handle
and return plain dicts/lists, keeping the search/kick responsibility here.
"""

import logging
import re

from librouteros.exceptions import TrapError

from core.mikrotik_client import MikrotikClient, RouterOSResponse, RouterOSRow
from utils.formatters import sanitize_log_data

logger = logging.getLogger(__name__)


# DHCP leases returned by RouterOS are loosely typed dicts.
LeaseDict = RouterOSRow


def get_leases_by_mac(api: MikrotikClient, router_key: str, macs: set[str]) -> dict[str, LeaseDict]:
    """Fetch DHCP leases and return a dict keyed by lower-case MAC address.

    Moved verbatim from ``HotspotManager._get_leases_by_mac`` so that search
    and kick functions can enrich host entries with DHCP lease host names.
    """
    leases: RouterOSResponse = api.execute(router_key, "ip/dhcp-server/lease/print")
    return {
        str(lease.get("mac-address", "")).lower(): lease
        for lease in leases
        if str(lease.get("mac-address", "")).lower() in macs
    }


def search_hosts(api: MikrotikClient, router_key: str, search_term: str) -> RouterOSResponse:  # noqa: C901
    """Search hotspot hosts by IP or MAC address with enriched host names from DHCP leases."""
    search_lower = search_term.lower().strip()
    hosts: RouterOSResponse = []

    proplist = (
        ".id,mac-address,address,user,bypassed,uptime,bytes-in,bytes-out,server"
    )
    try:
        hosts = api.execute(
            router_key,
            "ip/hotspot/host/print",
            **{"?mac-address": search_lower, ".proplist": proplist},
        )
    except (TrapError, ConnectionError, OSError):
        hosts = []
    except Exception:  # noqa: BLE001
        hosts = []

    if not hosts:
        try:
            hosts = api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?address": search_lower, ".proplist": proplist},
            )
        except (TrapError, ConnectionError, OSError):
            hosts = []
        except Exception:  # noqa: BLE001
            hosts = []

    if not hosts:
        try:
            all_hosts = api.execute(router_key, "ip/hotspot/host/print", **{".proplist": proplist})
            for h in all_hosts:
                mac = str(h.get("mac-address", "")).lower()
                ip = str(h.get("address", "")).lower()
                user = str(h.get("user", "")).lower()
                if search_lower in ip or search_lower in mac or search_lower in user:
                    hosts.append(h)
        except (TrapError, ConnectionError, OSError) as e:
            logger.warning(
                "Error fetching all hotspot hosts in search_hosts (query='%s', router='%s') "
                "(error type: %s): %s",
                search_lower, router_key,
                type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error fetching all hotspot hosts in search_hosts (query='%s', router='%s') "
                "(error type: %s): %s",
                search_lower, router_key,
                type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )

    if not hosts:
        return []

    matched_macs = {str(h.get("mac-address", "")).lower() for h in hosts if h.get("mac-address")}
    lease_by_mac = get_leases_by_mac(api, router_key, matched_macs)
    for h in hosts:
        mac = str(h.get("mac-address", "")).lower()
        lease = lease_by_mac.get(mac, {})
        h["host-name"] = lease.get("host-name", "")
    return hosts


def kick_host(api: MikrotikClient, router_key: str, mac_or_ip: str) -> tuple[bool, str | None]:
    """Remove a hotspot host by MAC or IP address."""
    target = mac_or_ip.lower().strip()
    hosts: RouterOSResponse = []

    proplist = ".id,mac-address,address,user"
    try:
        hosts = api.execute(
            router_key,
            "ip/hotspot/host/print",
            **{"?mac-address": target, ".proplist": proplist},
        )
        if not hosts:
            hosts = api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?address": target, ".proplist": proplist},
            )
    except (TrapError, ConnectionError, OSError) as e:
        logger.warning(
            "Error fetching host details for target '%s' in kick_host (router='%s') "
            "(error type: %s): %s",
            target, router_key,
            type(e).__name__, sanitize_log_data(str(e)),
            exc_info=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Error fetching host details for target '%s' in kick_host (router='%s') "
            "(error type: %s): %s",
            target, router_key,
            type(e).__name__, sanitize_log_data(str(e)),
            exc_info=True,
        )

    if not hosts:
        all_hosts = api.execute(router_key, "ip/hotspot/host/print", **{".proplist": proplist})
        for h in all_hosts:
            if (
                str(h.get("mac-address", "")).lower() == target
                or str(h.get("address", "")).lower() == target
            ):
                hosts.append(h)
                break

    if not hosts:
        return False, None

    h = hosts[0]
    mac = str(h.get("mac-address", "")).lower()
    ip = str(h.get("address", "")).lower()
    host_id = h.get(".id")

    lease_by_mac = get_leases_by_mac(api, router_key, {mac}) if mac else {}
    lease = lease_by_mac.get(mac, {})
    host_name = str(lease.get("host-name") or h.get("user") or mac or ip)

    api.execute(router_key, "ip/hotspot/host/remove", **{".id": host_id})
    return True, host_name


def _find_active_sessions(
    api: MikrotikClient,
    router_key: str,
    target: str,
) -> tuple[RouterOSResponse, set[str]]:
    """Find active hotspot sessions for *target* and kick them.

    Returns (kicked_sessions, macs_to_kick).
    """
    active_proplist = ".id,user,mac-address"
    try:
        active_sessions = api.execute(
            router_key,
            "ip/hotspot/active/print",
            **{"?user": target, ".proplist": active_proplist},
        )
    except (TrapError, ConnectionError, OSError):
        active = api.execute(
            router_key, "ip/hotspot/active/print", **{".proplist": active_proplist}
        )
        active_sessions = [s for s in active if str(s.get("user", "")).lower() == target]
    except Exception:  # noqa: BLE001
        active = api.execute(
            router_key, "ip/hotspot/active/print", **{".proplist": active_proplist}
        )
        active_sessions = [s for s in active if str(s.get("user", "")).lower() == target]

    macs_to_kick: set[str] = set()
    for s in active_sessions:
        mac = s.get("mac-address", "")
        if mac:
            macs_to_kick.add(str(mac).lower())
        api.execute(router_key, "ip/hotspot/active/remove", **{".id": s.get(".id")})
    return active_sessions, macs_to_kick


def _find_matched_hosts(
    api: MikrotikClient,
    router_key: str,
    target: str,
    is_mac_target: bool,
    macs_to_kick: set[str],
) -> RouterOSResponse:
    """Find host entries matching *target* or any of *macs_to_kick*."""
    host_proplist = ".id,mac-address,address,user"
    try:
        if is_mac_target:
            return api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?mac-address": target, ".proplist": host_proplist},
            )
        matched_hosts: RouterOSResponse = api.execute(
            router_key,
            "ip/hotspot/host/print",
            **{"?user": target, ".proplist": host_proplist},
        )
        for mac in macs_to_kick:
            mac_hosts = api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?mac-address": mac, ".proplist": host_proplist},
            )
            matched_hosts.extend(mac_hosts)
        return matched_hosts
    except (TrapError, ConnectionError, OSError):
        all_hosts = api.execute(router_key, "ip/hotspot/host/print", **{".proplist": host_proplist})
        return [
            h
            for h in all_hosts
            if (
                str(h.get("user", "")).lower() == target
                or str(h.get("mac-address", "")).lower() in macs_to_kick
                or (is_mac_target and str(h.get("mac-address", "")).lower() == target)
                or str(h.get("address", "")).lower() == target
            )
        ]
    except Exception:  # noqa: BLE001
        all_hosts = api.execute(router_key, "ip/hotspot/host/print", **{".proplist": host_proplist})
        return [
            h
            for h in all_hosts
            if (
                str(h.get("user", "")).lower() == target
                or str(h.get("mac-address", "")).lower() in macs_to_kick
                or (is_mac_target and str(h.get("mac-address", "")).lower() == target)
                or str(h.get("address", "")).lower() == target
            )
        ]


def kick_user(api: MikrotikClient, router_key: str, username: str) -> list[str]:
    """Kick an active hotspot user and remove all matching host entries."""
    target = str(username).lower().strip()
    is_mac_target = bool(re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", target))

    _, macs_to_kick = _find_active_sessions(api, router_key, target)
    matched_hosts = _find_matched_hosts(api, router_key, target, is_mac_target, macs_to_kick)

    unique_hosts = {h.get(".id"): h for h in matched_hosts if h.get(".id")}.values()
    if not unique_hosts:
        return []

    matched_macs = {
        str(h.get("mac-address", "")).lower() for h in unique_hosts if h.get("mac-address")
    }
    lease_by_mac = get_leases_by_mac(api, router_key, matched_macs)

    kicked: list[str] = []
    for h in unique_hosts:
        mac = str(h.get("mac-address", "")).lower()
        lease = lease_by_mac.get(mac, {})
        host_name = lease.get("host-name") or h.get("user") or mac or h.get("address", "")
        api.execute(router_key, "ip/hotspot/host/remove", **{".id": h.get(".id")})
        kicked.append(str(host_name))

    return list(set(kicked))
