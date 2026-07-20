"""Hotspot host/user search and kick operations.

Extracted from ``core.hotspot_manager`` so that user-lifecycle CRUD stays
separate from host discovery and active-session eviction. These functions
are pure with respect to the MikroTik API client: they take an API handle
and return plain dicts/lists, keeping the search/kick responsibility here.
"""

import re
import logging

logger = logging.getLogger(__name__)


def get_leases_by_mac(api, router_key: str, macs: set) -> dict[str, dict]:
    """Fetch DHCP leases and return a dict keyed by lower-case MAC address.

    Moved verbatim from ``HotspotManager._get_leases_by_mac`` so that search
    and kick functions can enrich host entries with DHCP lease host names.
    """
    leases = api.execute(router_key, "ip/dhcp-server/lease/print")
    return {
        str(lease.get("mac-address", "")).lower(): lease
        for lease in leases
        if str(lease.get("mac-address", "")).lower() in macs
    }


def search_hosts(api, router_key: str, search_term: str) -> list[dict]:
    """Search hotspot hosts by IP or MAC address with enriched host names from DHCP leases."""
    search_lower = search_term.lower().strip()
    hosts = []

    proplist = ".id,mac-address,address,host-name,user,bypass-bypassed,uptime,bytes-in,bytes-out,server"
    try:
        hosts = api.execute(
            router_key,
            "ip/hotspot/host/print",
            **{"?mac-address": search_lower, ".proplist": proplist},
        )
        if not hosts:
            hosts = api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?address": search_lower, ".proplist": proplist},
            )
    except Exception as e:
        logger.warning(f"Error searching hotspot hosts: {e}")

    if not hosts:
        all_hosts = api.execute(
            router_key, "ip/hotspot/host/print", **{".proplist": proplist}
        )
        for h in all_hosts:
            mac = str(h.get("mac-address", "")).lower()
            ip = str(h.get("address", "")).lower()
            if search_lower in ip or search_lower in mac:
                hosts.append(h)

    if not hosts:
        return []

    matched_macs = {
        str(h.get("mac-address", "")).lower() for h in hosts if h.get("mac-address")
    }
    lease_by_mac = get_leases_by_mac(api, router_key, matched_macs)
    for h in hosts:
        mac = str(h.get("mac-address", "")).lower()
        lease = lease_by_mac.get(mac, {})
        h["host-name"] = lease.get("host-name", "")
    return hosts


def kick_host(api, router_key: str, mac_or_ip: str) -> tuple[bool, str | None]:
    """Remove a hotspot host by MAC or IP address."""
    target = mac_or_ip.lower().strip()
    hosts = []

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
    except Exception as e:
        logger.warning(f"Error fetching host details for '{target}': {e}")

    if not hosts:
        all_hosts = api.execute(
            router_key, "ip/hotspot/host/print", **{".proplist": proplist}
        )
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
    host_name = lease.get("host-name") or h.get("user") or mac or ip

    api.execute(router_key, "ip/hotspot/host/remove", **{".id": host_id})
    return True, host_name


def kick_user(api, router_key: str, username: str) -> list[str]:
    """Kick an active hotspot user and remove all matching host entries."""
    target = str(username).lower().strip()
    is_mac_target = bool(re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", target))

    kicked = []
    macs_to_kick = set()

    active_sessions = []
    active_proplist = ".id,user,mac-address"
    try:
        active_sessions = api.execute(
            router_key,
            "ip/hotspot/active/print",
            **{"?user": target, ".proplist": active_proplist},
        )
    except Exception:
        active = api.execute(
            router_key, "ip/hotspot/active/print", **{".proplist": active_proplist}
        )
        active_sessions = [
            s for s in active if str(s.get("user", "")).lower() == target
        ]

    for s in active_sessions:
        mac = s.get("mac-address", "")
        if mac:
            macs_to_kick.add(mac.lower())
        api.execute(router_key, "ip/hotspot/active/remove", **{".id": s.get(".id")})

    matched_hosts = []
    host_proplist = ".id,mac-address,address,user"
    try:
        if is_mac_target:
            matched_hosts = api.execute(
                router_key,
                "ip/hotspot/host/print",
                **{"?mac-address": target, ".proplist": host_proplist},
            )
        else:
            matched_hosts = api.execute(
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
    except Exception:
        all_hosts = api.execute(
            router_key, "ip/hotspot/host/print", **{".proplist": host_proplist}
        )
        for h in all_hosts:
            mac = str(h.get("mac-address", "")).lower()
            ip = str(h.get("address", "")).lower()
            if (
                str(h.get("user", "")).lower() == target
                or mac in macs_to_kick
                or (is_mac_target and mac == target)
                or ip == target
            ):
                matched_hosts.append(h)

    unique_hosts = {h.get(".id"): h for h in matched_hosts if h.get(".id")}.values()

    if not unique_hosts:
        return []

    matched_macs = {
        str(h.get("mac-address", "")).lower()
        for h in unique_hosts
        if h.get("mac-address")
    }
    lease_by_mac = get_leases_by_mac(api, router_key, matched_macs)

    for h in unique_hosts:
        mac = str(h.get("mac-address", "")).lower()
        host_id = h.get(".id")
        lease = lease_by_mac.get(mac, {})
        host_name = (
            lease.get("host-name") or h.get("user") or mac or h.get("address", "")
        )

        api.execute(router_key, "ip/hotspot/host/remove", **{".id": host_id})
        kicked.append(host_name)

    return list(set(kicked))