import re
import logging
import secrets
import string
from datetime import datetime
from librouteros.exceptions import LibRouterosError
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient
from core.card_models import CardData, CardSystem
from utils.formatters import format_bytes, parse_bytes
from core.cache import TTLCache

logger = logging.getLogger(__name__)

_GB = 1_000_000_000

_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


class HotspotManager:
    """Manages MikroTik Hotspot users, hosts, profiles, and session kick operations."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api
        self._users_cache = TTLCache(max_size=20, ttl=5)
        self._profiles_cache = TTLCache(max_size=20, ttl=10)

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def _generate_random_number(self, length: int) -> str:
        """Generate a cryptographically secure random number of specified length."""
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    def _get_all_users_cached(self, router_key: str) -> list[dict]:
        cached = self._users_cache.get(router_key)
        if cached is not None:
            return cached
        users = self._api.execute(router_key, "ip/hotspot/user/print")
        self._users_cache.set(router_key, users)
        return users

    def invalidate_users_cache(self, router_key: str):
        self._users_cache.invalidate(router_key)

    def _get_existing_usernames(self, router_key: str) -> set:
        """Fetch all existing hotspot usernames from the router."""
        users = self._get_all_users_cached(router_key)
        return {u.get("name", "") for u in users if isinstance(u, dict)}


    def user_exists(self, router_key: str, name: str) -> bool:
        """Return True if a hotspot user with the given name already exists on the router.

        Uses an API-side ``?name=`` filter to avoid pulling the full user list.
        On any transport/API error it returns False so callers fall back to the
        defensive duplicate check performed by ``add_user`` at write time.
        """
        name = (name or "").strip()
        if not name:
            return False
        try:
            users = self._api.execute(router_key, "ip/hotspot/user/print", **{"?name": name})
            return any(u.get("name") == name for u in users if isinstance(u, dict))
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error(f"Failed to check user existence for '{name}': {e}")
            return False

    def _generate_unique_username(self, prefix: str, length: int, existing_names: set) -> str:
        """Generate a unique username that doesn't exist on the router."""
        max_attempts = 100
        for _ in range(max_attempts):
            random_num = self._generate_random_number(length)
            username = f"{prefix}{random_num}" if prefix else random_num
            if username not in existing_names:
                return username
        raise ValueError(f"Failed to generate unique username after {max_attempts} attempts")

    def add_user(self, router_key: str, name: str, password: str, profile: str,
                 bytes_total: str = "", uptime: str = "", comment: str = "") -> list[dict]:
        """Add a new hotspot user with optional bandwidth limit, uptime limit, and comment."""
        params = {
            "name": name,
            "profile": profile,
        }
        if password:
            params["password"] = password
        if bytes_total:
            params["limit-bytes-total"] = bytes_total
        if uptime:
            params["limit-uptime"] = uptime
        if comment:
            params["comment"] = comment

        result = self._api.execute(router_key, "ip/hotspot/user/add", **params)
        self.invalidate_users_cache(router_key)
        logger.info(f"Added hotspot user '{name}' on {router_key}")
        return result

    def edit_user(self, router_key: str, user_id: str, **kwargs: object) -> list[dict]:
        """Update allowed fields of an existing hotspot user by its .id."""
        params = {".id": user_id}
        allowed_fields = ["name", "password", "profile", "limit-bytes-total", "limit-uptime", "comment", "disabled"]
        for key, value in kwargs.items():
            normalized = key.replace("_", "-")
            if normalized in allowed_fields and value is not None:
                params[normalized] = value if isinstance(value, str) else str(value)

        result = self._api.execute(router_key, "ip/hotspot/user/set", **params)
        self.invalidate_users_cache(router_key)
        logger.info(f"Edited hotspot user {user_id} on {router_key}")
        return result

    def reset_user_counters(self, router_key: str, user_id: str) -> list[dict]:
        """Reset traffic counters for a hotspot user."""
        result = self._api.execute(
            router_key, "ip/hotspot/user/reset-counters", **{"numbers": user_id}
        )
        self.invalidate_users_cache(router_key)
        logger.info(f"Reset counters for hotspot user {user_id} on {router_key}")
        return result

    def enable_user(self, router_key: str, user_id: str) -> list[dict]:
        """Enable a hotspot user by its .id."""
        result = self._api.execute(
            router_key, "ip/hotspot/user/enable", **{"numbers": user_id}
        )
        self.invalidate_users_cache(router_key)
        logger.info(f"Enabled hotspot user {user_id} on {router_key}")
        return result

    def disable_user(self, router_key: str, user_id: str) -> list[dict]:
        """Disable a hotspot user by its .id."""
        result = self._api.execute(
            router_key, "ip/hotspot/user/disable", **{"numbers": user_id}
        )
        self.invalidate_users_cache(router_key)
        logger.info(f"Disabled hotspot user {user_id} on {router_key}")
        return result

    def delete_user(self, router_key: str, user_id: str) -> list[dict]:
        """Delete a hotspot user by its .id."""
        result = self._api.execute(
            router_key, "ip/hotspot/user/remove", **{".id": user_id}
        )
        self.invalidate_users_cache(router_key)
        logger.info(f"Deleted hotspot user {user_id} on {router_key}")
        return result

    def search_users(self, router_key: str, search_term: str) -> list[dict]:
        """Search hotspot users by name or comment (case-insensitive substring match).

        Uses API-side ?name= and ?comment= filters when possible, with automatic
        fallback to in-memory filtering if the RouterOS version doesn't support it.
        """
        search = search_term.lower()
        seen = set()
        results = []

        for field in ("name", "comment"):
            try:
                batch = self._api.execute(router_key, "ip/hotspot/user/print", **{
                    f"?{field}": f"*{search}*"
                })
                for user in batch:
                    uid = user.get(".id")
                    if uid and uid not in seen:
                        seen.add(uid)
                        results.append(user)
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.debug("API-side filtered search for '%s' on %s failed: %s", search, field, e)

        if not results:
            all_users = self._get_all_users_cached(router_key)
            for user in all_users:
                name = str(user.get("name", "")).lower()
                comment = str(user.get("comment", "")).lower()
                if search in name or search in comment:
                    results.append(user)

        return results

    def search_hosts(self, router_key: str, search_term: str) -> list[dict]:
        """Search hotspot hosts by IP or MAC address with enriched host names from DHCP leases."""
        search_lower = search_term.lower().strip()
        hosts = []
        
        try:
            hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?mac-address": search_lower})
            if not hosts:
                hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?address": search_lower})
        except Exception as e:
            logger.warning(f"Error searching hotspot hosts: {e}")

        if not hosts:
            all_hosts = self._api.execute(router_key, "ip/hotspot/host/print")
            for h in all_hosts:
                mac = str(h.get("mac-address", "")).lower()
                ip = str(h.get("address", "")).lower()
                if search_lower in ip or search_lower in mac:
                    hosts.append(h)

        if not hosts:
            return []

        matched_macs = {str(h.get("mac-address", "")).lower() for h in hosts if h.get("mac-address")}
        lease_by_mac = self._get_leases_by_mac(router_key, matched_macs)
        for h in hosts:
            mac = str(h.get("mac-address", "")).lower()
            lease = lease_by_mac.get(mac, {})
            h["host-name"] = lease.get("host-name", "")
        return hosts

    def kick_host(self, router_key: str, mac_or_ip: str) -> tuple[bool, str | None]:
        """Remove a hotspot host by MAC or IP address."""
        target = mac_or_ip.lower().strip()
        hosts = []
        
        try:
            hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?mac-address": target})
            if not hosts:
                hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?address": target})
        except Exception as e:
            logger.warning(f"Error fetching host details for '{target}': {e}")
            
        if not hosts:
            all_hosts = self._api.execute(router_key, "ip/hotspot/host/print")
            for h in all_hosts:
                if str(h.get("mac-address", "")).lower() == target or str(h.get("address", "")).lower() == target:
                    hosts.append(h)
                    break

        if not hosts:
            return False, None
            
        h = hosts[0]
        mac = str(h.get("mac-address", "")).lower()
        ip = str(h.get("address", "")).lower()
        host_id = h.get(".id")
        
        lease_by_mac = self._get_leases_by_mac(router_key, {mac}) if mac else {}
        lease = lease_by_mac.get(mac, {})
        host_name = lease.get("host-name") or h.get("user") or mac or ip
        
        self._api.execute(router_key, "ip/hotspot/host/remove", **{".id": host_id})
        return True, host_name

    def kick_user(self, router_key: str, username: str) -> list[str]:
        """Kick an active hotspot user and remove all matching host entries."""
        target = str(username).lower().strip()
        is_mac_target = bool(re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', target))

        kicked = []
        macs_to_kick = set()
        
        active_sessions = []
        try:
            active_sessions = self._api.execute(router_key, "ip/hotspot/active/print", **{"?user": target})
        except Exception:
            active = self._api.execute(router_key, "ip/hotspot/active/print")
            active_sessions = [s for s in active if str(s.get("user", "")).lower() == target]
            
        for s in active_sessions:
            mac = s.get("mac-address", "")
            if mac:
                macs_to_kick.add(mac.lower())
            self._api.execute(router_key, "ip/hotspot/active/remove", **{".id": s.get(".id")})

        matched_hosts = []
        try:
            if is_mac_target:
                matched_hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?mac-address": target})
            else:
                matched_hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?user": target})
                for mac in macs_to_kick:
                    mac_hosts = self._api.execute(router_key, "ip/hotspot/host/print", **{"?mac-address": mac})
                    matched_hosts.extend(mac_hosts)
        except Exception:
            all_hosts = self._api.execute(router_key, "ip/hotspot/host/print")
            for h in all_hosts:
                mac = str(h.get("mac-address", "")).lower()
                ip = str(h.get("address", "")).lower()
                if str(h.get("user", "")).lower() == target or mac in macs_to_kick or (is_mac_target and mac == target) or ip == target:
                    matched_hosts.append(h)

        unique_hosts = {h.get(".id"): h for h in matched_hosts if h.get(".id")}.values()
        
        if not unique_hosts:
            return []

        matched_macs = {str(h.get("mac-address", "")).lower() for h in unique_hosts if h.get("mac-address")}
        lease_by_mac = self._get_leases_by_mac(router_key, matched_macs)
        
        for h in unique_hosts:
            mac = str(h.get("mac-address", "")).lower()
            host_id = h.get(".id")
            lease = lease_by_mac.get(mac, {})
            host_name = lease.get("host-name") or h.get("user") or mac or h.get("address", "")
            
            self._api.execute(router_key, "ip/hotspot/host/remove", **{".id": host_id})
            kicked.append(host_name)
            
        return list(set(kicked))

    def list_users(self, router_key: str, limit: int = 50) -> list[dict]:
        """Return up to limit hotspot users from the router."""
        all_users = self._get_all_users_cached(router_key)
        return all_users[:limit] if all_users else []

    def get_user(self, router_key: str, user_id: str) -> dict | None:
        """Return a single hotspot user dict by its .id, or None if not found."""
        all_users = self._get_all_users_cached(router_key)
        for user in all_users:
            if user.get(".id") == user_id:
                return user
        return None

    def _get_leases_by_mac(self, router_key: str, macs: set) -> dict[str, dict]:
        """Fetch DHCP leases and return a dict keyed by lower-case MAC address."""
        leases = self._api.execute(router_key, "ip/dhcp-server/lease/print")
        return {
            str(lease.get("mac-address", "")).lower(): lease
            for lease in leases
            if str(lease.get("mac-address", "")).lower() in macs
        }

    def get_profiles(self, router_key: str) -> list[dict]:
        """Return list of hotspot user profiles from the router."""
        cached = self._profiles_cache.get(router_key)
        if cached is not None:
            return cached
        try:
            results = self._api.execute(router_key, "ip/hotspot/user/profile/print")
            self._profiles_cache.set(router_key, results)
            return results
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error("Failed to fetch hotspot profiles: %s", e)
            return []

    def create_cards(self, router_key: str, count: int, length: int,
                     card_system: CardSystem, profile: str,
                     prefix: str = "", limit_uptime: str = "",
                     limit_bytes: str = "") -> list[CardData]:
        """Create multiple hotspot users with random numbers and duplicate checking."""
        cards = []
        base_time = datetime.now().strftime("%Y-%m-%d_%H:%M")
        batch_comment = f"{prefix}_{base_time}" if prefix else base_time

        existing_names = self._get_existing_usernames(router_key)

        for i in range(1, count + 1):
            try:
                username = self._generate_unique_username(prefix, length, existing_names)
                existing_names.add(username)

                if card_system == CardSystem.DIFFERENT_CREDENTIALS:
                    password = self._generate_random_number(length)
                elif card_system == CardSystem.SAME_CREDENTIALS:
                    password = username
                else:
                    password = ""

                self.add_user(
                    router_key=router_key,
                    name=username,
                    password=password,
                    profile=profile,
                    bytes_total=limit_bytes,
                    uptime=limit_uptime,
                    comment=batch_comment,
                )
                cards.append(CardData(
                    username=username,
                    password=password,
                    card_number=i,
                    profile=profile,
                    limit_uptime=limit_uptime,
                    limit_bytes=limit_bytes,
                    comment=batch_comment
                ))
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.error(f"Failed to create card user at index {i}: {e}")

        self.invalidate_users_cache(router_key)
        return cards

    def format_user(self, user: dict) -> str:
        """Format a hotspot user dict into a human-readable Arabic string."""
        bytes_in = user.get('bytes-in', '0')
        bytes_out = user.get('bytes-out', '0')
        try:
            total_consumed = int(bytes_in) + int(bytes_out)
            total_text = format_bytes(str(total_consumed))
        except (ValueError, TypeError):
            total_text = 'غير معروف'
        
        uptime_raw = user.get('limit-uptime', '')
        uptime_text = uptime_raw if uptime_raw else 'غير محدود'
        
        lines = [
            f"\U0001f464 الاسم: {user.get('name', 'لا يوجد')}",
            f"\U0001f511 الباسورد: {'*' * 8 if user.get('password') else 'لا يوجد'}",
            f"\U0001f4cb البروفايل: {user.get('profile', 'لا يوجد')}",
            f"\U0001f4ca الحد: {format_bytes(user.get('limit-bytes-total', ''))}",
            f"\u23f0 المدة: {uptime_text}",
            f"\U0001f4ca المستهلك: {total_text}",
            f"\U0001f4ac التعليق: {user.get('comment', 'لا يوجد')}",
            f"\U0001f194 الرقم: {user.get('.id', 'لا يوجد')}",
        ]
        return '\n'.join(lines)

    def _parse_reset_day(self, comment: str) -> int | None:
        """Extract the reset day (1-31) from a hotspot user comment.

        Supports the current ``PREFIX_YYYY-MM-DD_HH:MM`` batch format as well as
        the legacy ``.../DD`` format. Returns ``None`` when no day is found.
        """
        comment = str(comment or "")
        match = _DATE_RE.search(comment)
        if match:
            try:
                return int(match.group(3))
            except (ValueError, TypeError):
                return None
        if "/" in comment:
            try:
                return int(comment.split("/")[-1])
            except (ValueError, TypeError):
                return None
        return None

    def get_hotspot_stats(self, router_key: str, day: int | None = None) -> dict | None:
        """Return hotspot statistics, optionally filtered to a single reset day.

        When ``day`` is ``None`` the ``reset_list`` is empty and ``reset_days``
        exposes every day that has reset records so the UI can offer a picker.
        When ``day`` is provided, ``reset_list`` contains only that day's resets.
        """
        try:
            users = self.list_users(router_key, limit=1000)

            active_count = 0
            inactive_count = 0
            categories = {"10 GB": 0, "20 GB": 0, "30 GB": 0, "40 GB": 0, "50 GB": 0, "أخرى": 0}
            resets_by_day: dict[int, list[tuple[str, str]]] = {}

            for user in users:
                is_disabled = str(user.get("disabled", "false")).lower() == "true"

                if is_disabled:
                    inactive_count += 1
                else:
                    active_count += 1

                    limit_raw = user.get("limit-bytes-total", "")
                    if limit_raw and str(limit_raw) != "0":
                        try:
                            limit_str = str(limit_raw)
                            limit_bytes = int(parse_bytes(limit_str)) if not limit_str.isdigit() else int(limit_str)
                            limit_gb = limit_bytes / _GB
                            if 10 <= limit_gb < 20:
                                categories["10 GB"] += 1
                            elif 20 <= limit_gb < 30:
                                categories["20 GB"] += 1
                            elif 30 <= limit_gb < 40:
                                categories["30 GB"] += 1
                            elif 40 <= limit_gb < 50:
                                categories["50 GB"] += 1
                            elif limit_gb >= 50:
                                categories["50 GB"] += 1
                            else:
                                categories["أخرى"] += 1
                        except (ValueError, TypeError):
                            categories["أخرى"] += 1
                    else:
                        categories["أخرى"] += 1

                if not is_disabled:
                    reset_day = self._parse_reset_day(user.get("comment", ""))
                    if reset_day is not None:
                        limit = format_bytes(user.get("limit-bytes-total", ""))
                        resets_by_day.setdefault(reset_day, []).append(
                            (str(user.get("comment", "")), limit)
                        )

            reset_days = sorted(resets_by_day.keys(), reverse=True)
            if day is None:
                reset_list: list[tuple[str, str]] = []
                selected_day = None
            else:
                reset_list = resets_by_day.get(day, [])
                selected_day = day

            return {
                "total": len(users),
                "active": active_count,
                "inactive": inactive_count,
                "categories": categories,
                "resets_by_day": resets_by_day,
                "reset_days": reset_days,
                "reset_list": reset_list,
                "selected_day": selected_day,
            }
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error(f"Error getting hotspot stats: {e}")
            return None

    def build_usage_report(self, router_key: str, top_n: int = 15) -> dict:
        """Build an exportable Hotspot usage report for a router.

        Fetches all hotspot users (long-running call) and classifies them into
        summary statistics, top consumers, expired, near-limit and inactive groups.
        Returns a plain dict with a flat ``rows`` list suitable for CSV export.
        """
        users = self._api.execute_long(router_key, "ip/hotspot/user/print")

        rows: list[dict] = []
        total_bytes_all = 0
        active_count = 0
        disabled_count = 0
        with_limit_count = 0

        for u in users:
            if not isinstance(u, dict):
                continue
            name = u.get("name", "")
            profile = u.get("profile", "")
            is_disabled = str(u.get("disabled", "false")).lower() == "true"
            if is_disabled:
                disabled_count += 1
            else:
                active_count += 1

            try:
                bytes_in = int(u.get("bytes-in", 0) or 0)
            except (ValueError, TypeError):
                bytes_in = 0
            try:
                bytes_out = int(u.get("bytes-out", 0) or 0)
            except (ValueError, TypeError):
                bytes_out = 0

            total_bytes = bytes_in + bytes_out
            total_bytes_all += total_bytes

            limit_raw = u.get("limit-bytes-total", "")
            limit = 0
            if limit_raw and str(limit_raw) not in ("0", "0.0", ""):
                try:
                    limit = int(limit_raw)
                except (ValueError, TypeError):
                    limit = 0
            if limit > 0:
                with_limit_count += 1

            percent = (total_bytes / limit * 100) if limit > 0 else 0.0
            comment = u.get("comment", "")

            rows.append({
                "name": name,
                "profile": profile,
                "status": "disabled" if is_disabled else "active",
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
                "total_bytes": total_bytes,
                "total_str": format_bytes(str(total_bytes)),
                "limit": limit,
                "limit_str": format_bytes(str(limit)) if limit else "—",
                "percent": percent,
                "comment": comment,
            })

        top_consumers = sorted(rows, key=lambda r: r["total_bytes"], reverse=True)[:top_n]
        expired = [r for r in rows if r["limit"] > 0 and r["total_bytes"] >= r["limit"]]
        near_limit = [r for r in rows if r["limit"] > 0 and 90 <= r["percent"] < 100]
        inactive = [r for r in rows if r["status"] == "disabled"]

        return {
            "router_key": router_key,
            "total": len(rows),
            "active": active_count,
            "disabled": disabled_count,
            "with_limit": with_limit_count,
            "total_bytes": total_bytes_all,
            "total_bytes_str": format_bytes(str(total_bytes_all)),
            "top_consumers": top_consumers,
            "expired": expired,
            "near_limit": near_limit,
            "inactive": inactive,
            "rows": rows,
        }


    def block_mac(self, router_key: str, mac: str, comment: str = "blocked by bot") -> bool:
        """يضيف MAC إلى address-list باسم hotspot_blocked في /ip/firewall/address-list.

        يُعيد True عند النجاح وFalse عند الفشل.
        ملاحظة: يحتاج إلى firewall rule منفصلة لحظر الاتصال فعلياً.
        """
        try:
            self._api.execute(
                router_key,
                "ip/firewall/address-list/add",
                address=mac,
                list="hotspot_blocked",
                comment=comment,
            )
            logger.info(f"Blocked MAC {mac} on {router_key}")
            return True
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error(f"Failed to block MAC {mac} on {router_key}: {e}")
            return False

    def unblock_mac(self, router_key: str, mac: str) -> bool:
        """يحذف MAC من address-list=hotspot_blocked.

        يُعيد True عند النجاح وFalse عند الفشل أو عدم الوجود.
        """
        try:
            entries = self._api.execute(
                router_key,
                "ip/firewall/address-list/print",
                **{"?list": "hotspot_blocked", "?address": mac},
            )
            if not entries:
                logger.info(f"MAC {mac} not found in blocked list on {router_key}")
                return False
            entry_id = entries[0].get(".id")
            if not entry_id:
                return False
            self._api.execute(
                router_key,
                "ip/firewall/address-list/remove",
                **{".id": entry_id},
            )
            logger.info(f"Unblocked MAC {mac} on {router_key}")
            return True
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error(f"Failed to unblock MAC {mac} on {router_key}: {e}")
            return False

    def get_blocked_macs(self, router_key: str) -> list[dict]:
        """يُعيد قائمة MACs في address-list=hotspot_blocked.

        يُعيد قائمة فارغة عند الفشل.
        """
        try:
            entries = self._api.execute(
                router_key,
                "ip/firewall/address-list/print",
                **{"?list": "hotspot_blocked"},
            )
            return [
                {
                    "address": e.get("address", ""),
                    "comment": e.get("comment", ""),
                    "creation-time": e.get("creation-time", ""),
                }
                for e in entries if isinstance(e, dict)
            ]
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.warning(f"Failed to get blocked MACs on {router_key}: {e}")
            return []

    def get_expiring_users(self, router_key: str, days: int = 3) -> list[dict]:
        """إعادة قائمة المستخدمين الذين ستنتهي صلاحيتهم خلال `days` أيام.

        يعتمد على `limit-uptime` في RouterOS:
        - RouterOS يحسب `limit-uptime` من لحظة أول اتصال ناجح للمستخدم
          (يُنقص منه `uptime` للجلسات النشطة).
        - نقارن `limit-uptime` بـ `uptime` المتراكمة من `ip/hotspot/active/print`
          لمعرفة كم تبقى.
        - إذا لم يكن للمستخدم جلسة نشطة نحسب بافتراض worst-case (استخدم كله).
        - المستخدمون ذوو `limit-uptime = 0` أو فارغ مُستثنَون.

        يُعيد قائمة دوال بـ: name, profile, uptime_limit, remaining_days, uptime_used
        """
        def _parse_uptime_to_seconds(raw: str) -> int:
            """تحويل `1d02:30:00` أو `00:30:00` إلى ثوانٍ. يُعيد 0 عند الفشل."""
            if not raw or raw in ("0", "0s", ""):
                return 0
            try:
                import re as _re
                # صيغة: [Nd]HH:MM:SS
                m = _re.match(r"(?:(\d+)d)?(?:(\d+):)?(\d+):(\d+)", str(raw))
                if not m:
                    return 0
                d = int(m.group(1) or 0)
                h = int(m.group(2) or 0)
                mn = int(m.group(3) or 0)
                s = int(m.group(4) or 0)
                return d * 86400 + h * 3600 + mn * 60 + s
            except Exception:
                return 0

        result: list[dict] = []
        try:
            users = self._api.execute(router_key, "ip/hotspot/user/print")
            # جلب الجلسات النشطة لمعرفة وقت الاستخدام الفعلي
            try:
                active_sessions = self._api.execute(router_key, "ip/hotspot/active/print")
                active_map: dict[str, int] = {}
                for sess in active_sessions:
                    if isinstance(sess, dict):
                        uname = sess.get("user", "")
                        uptime_secs = _parse_uptime_to_seconds(sess.get("uptime", ""))
                        active_map[uname] = active_map.get(uname, 0) + uptime_secs
            except Exception:
                active_map = {}

            for user in users:
                if not isinstance(user, dict):
                    continue
                # تخطي المستخدمين المعطلين
                if str(user.get("disabled", "false")).lower() == "true":
                    continue
                limit_raw = user.get("limit-uptime", "")
                limit_secs = _parse_uptime_to_seconds(limit_raw)
                if limit_secs <= 0:
                    continue
                name = user.get("name", "")
                # uptime_used = ما استُهلك من حد المستخدم (من الجلسات النشطة)
                used_secs = active_map.get(name, 0)
                remaining_secs = max(0, limit_secs - used_secs)
                remaining_days = remaining_secs / 86400
                if remaining_days <= days:
                    result.append({
                        "name": name,
                        "profile": user.get("profile", "—"),
                        "uptime_limit": limit_raw,
                        "remaining_days": round(remaining_days, 1),
                        "uptime_used_secs": used_secs,
                    })
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.warning(f"get_expiring_users failed for {router_key}: {e}")
        return sorted(result, key=lambda x: x["remaining_days"])


hotspot_manager = HotspotManager()
