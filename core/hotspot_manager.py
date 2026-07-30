import logging
import re
import secrets
import string
import threading
from datetime import datetime
from typing import cast

from librouteros.exceptions import TrapError

from core.cache import TTLCache
from core.card_models import CardData, CardSystem
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient, RouterOSResponse, RouterOSRow
from utils.formatters import sanitize_log_data
from utils.validators import sanitize_comment

logger = logging.getLogger(__name__)

_GB = 1_000_000_000

_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def _parse_uptime_seconds(val: str) -> int:
    """Parse RouterOS uptime string (e.g. '1d2h3m4s', '24:00:00', '3600s') to seconds."""
    if not val:
        return 0
    total = 0
    d_match = re.search(r"(\d+)d", val)
    h_match = re.search(r"(\d+)h", val)
    m_match = re.search(r"(\d+)m", val)
    s_match = re.search(r"(\d+)s", val)
    if d_match or h_match or m_match or s_match:
        if d_match:
            total += int(d_match.group(1)) * 86400
        if h_match:
            total += int(h_match.group(1)) * 3600
        if m_match:
            total += int(m_match.group(1)) * 60
        if s_match:
            total += int(s_match.group(1))
        return total
    parts = val.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(val)
    except ValueError:
        return 0


class HotspotManager:
    """Manages MikroTik Hotspot users, hosts, profiles, and session kick operations."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api
        self._users_cache = TTLCache(max_size=20, ttl=5)
        self._profiles_cache = TTLCache(max_size=20, ttl=10)
        self._card_creation_locks: dict[str, threading.Lock] = {}
        self._card_lock_lock = threading.Lock()

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def _generate_random_number(self, length: int) -> str:
        """Generate a cryptographically secure random number of specified length."""
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def _get_all_users_cached(self, router_key: str) -> RouterOSResponse:
        from typing import cast

        cached = self._users_cache.get(router_key)
        if cached is not None:
            return cast(RouterOSResponse, cached)
        # نجلب جميع الحقول المطلوبة للعرض والبحث
        proplist = ".id,name,profile,disabled,limit-uptime,limit-bytes-total,comment,bytes-in,bytes-out,uptime,password"
        users = self._api.execute(
            router_key, "ip/hotspot/user/print", **{".proplist": proplist}
        )
        self._users_cache.set(router_key, users)
        return users

    def invalidate_users_cache(self, router_key: str):
        self._users_cache.invalidate(router_key)

    def _get_existing_usernames(self, router_key: str) -> set[str]:
        """Fetch all existing hotspot usernames from the router."""
        users = self._get_all_users_cached(router_key)
        return {str(u.get("name", "")) for u in users}

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
            users = self._api.execute(
                router_key,
                "ip/hotspot/user/print",
                **{"?name": name, ".proplist": ".id"},
            )
            return len(users) > 0
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Failed to check user existence for '%s' in user_exists (router='%s') "
                "(error type: %s): %s",
                name, router_key, type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )
            return False
        except Exception as e:  # noqa: BLE001
            logger.exception(
                "Failed to check user existence for '%s' in user_exists (router='%s') "
                "(error type: %s): %s",
                name, router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return False

    def _generate_unique_username(self, prefix: str, length: int, existing_names: set[str]) -> str:
        """Generate a unique username that doesn't exist on the router."""
        max_attempts = 100
        for _ in range(max_attempts):
            random_num = self._generate_random_number(length)
            username = f"{prefix}{random_num}" if prefix else random_num
            if username not in existing_names:
                return username
        raise ValueError(f"Failed to generate unique username after {max_attempts} attempts")

    def add_user(
        self,
        router_key: str,
        name: str,
        password: str,
        profile: str,
        bytes_total: str = "",
        uptime: str = "",
        comment: str = "",
    ) -> RouterOSResponse:
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
            params["comment"] = sanitize_comment(comment)

        result = self._api.execute(router_key, "ip/hotspot/user/add", **params)
        self.invalidate_users_cache(router_key)
        logger.info("Added hotspot user '%s' on %s", name, router_key)
        return result

    def edit_user(self, router_key: str, user_id: str, **kwargs: object) -> RouterOSResponse:
        """Update allowed fields of an existing hotspot user by its .id."""
        params = {".id": user_id}
        allowed_fields = [
            "name",
            "password",
            "profile",
            "limit-bytes-total",
            "limit-uptime",
            "comment",
            "disabled",
        ]
        for key, value in kwargs.items():
            normalized = key.replace("_", "-")
            if normalized in allowed_fields and value is not None:
                if normalized == "comment":
                    params[normalized] = sanitize_comment(str(value))
                else:
                    params[normalized] = value if isinstance(value, str) else str(value)

        result = self._api.execute(router_key, "ip/hotspot/user/set", **params)
        self.invalidate_users_cache(router_key)
        logger.info("Edited hotspot user %s on %s", user_id, router_key)
        return result

    def reset_user_counters(self, router_key: str, user_id: str) -> RouterOSResponse:
        """Reset traffic counters for a hotspot user."""
        result = self._api.execute(
            router_key, "ip/hotspot/user/reset-counters", **{"numbers": user_id}
        )
        self.invalidate_users_cache(router_key)
        logger.info("Reset counters for hotspot user %s on %s", user_id, router_key)
        return result

    def enable_user(self, router_key: str, user_id: str) -> RouterOSResponse:
        """Enable a hotspot user by its .id."""
        result = self._api.execute(router_key, "ip/hotspot/user/enable", **{"numbers": user_id})
        self.invalidate_users_cache(router_key)
        logger.info("Enabled hotspot user %s on %s", user_id, router_key)
        return result

    def disable_user(self, router_key: str, user_id: str) -> RouterOSResponse:
        """Disable a hotspot user by its .id."""
        result = self._api.execute(router_key, "ip/hotspot/user/disable", **{"numbers": user_id})
        self.invalidate_users_cache(router_key)
        logger.info("Disabled hotspot user %s on %s", user_id, router_key)
        return result

    def delete_user(self, router_key: str, user_id: str) -> RouterOSResponse:
        """Delete a hotspot user by its .id."""
        result = self._api.execute(router_key, "ip/hotspot/user/remove", **{".id": user_id})
        self.invalidate_users_cache(router_key)
        logger.info("Deleted hotspot user %s on %s", user_id, router_key)
        return result

    def search_users(self, router_key: str, search_term: str) -> RouterOSResponse:
        """Search hotspot users by name or comment (case-insensitive substring match).

        Uses API-side ?name= and ?comment= filters when possible, with automatic
        fallback to in-memory filtering if the RouterOS version doesn't support it.
        """
        search = search_term.lower()
        seen: set[str] = set()
        results: RouterOSResponse = []

        for field in ("name", "comment"):
            try:
                batch = self._api.execute(
                    router_key,
                    "ip/hotspot/user/print",
                    **{
                        f"?{field}": f"*{search}*",
                        ".proplist": (
                            ".id,name,profile,disabled,limit-uptime,limit-bytes-total,"
                            "comment,bytes-in,bytes-out,uptime,password"
                        ),
                    },
                )
                for user in batch:
                    uid = user.get(".id")
                    if uid and str(uid) not in seen:
                        seen.add(str(uid))
                        results.append(user)
            except (TrapError, ConnectionError, OSError) as e:
                logger.debug(
                    "API-side filtered search for '%s' on %s failed "
                    "(error type: %s): %s",
                    search, field, type(e).__name__, sanitize_log_data(str(e)),
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "API-side filtered search for '%s' on %s failed "
                    "(error type: %s): %s",
                    search, field, type(e).__name__, sanitize_log_data(str(e)),
                )

        if not results:
            all_users = self._get_all_users_cached(router_key)
            for user in all_users:
                name = str(user.get("name", "")).lower()
                comment = str(user.get("comment", "")).lower()
                if search in name or search in comment:
                    results.append(user)

        return results

    def search_hosts(self, router_key: str, search_term: str) -> list[RouterOSRow]:
        """Search hotspot hosts by IP or MAC address with enriched host names from DHCP leases.

        Delegates to ``core.hotspot_search.search_hosts``.
        """
        from core.hotspot_search import search_hosts as _fn

        return _fn(self._api, router_key, search_term)

    def kick_host(self, router_key: str, mac_or_ip: str) -> tuple[bool, str | None]:
        """Remove a hotspot host by MAC or IP address.

        Delegates to ``core.hotspot_search.kick_host``.
        """
        from core.hotspot_search import kick_host as _fn

        return _fn(self._api, router_key, mac_or_ip)

    def kick_user(self, router_key: str, username: str) -> list[str]:
        """Kick an active hotspot user and remove all matching host entries.

        Delegates to ``core.hotspot_search.kick_user``.
        """
        from core.hotspot_search import kick_user as _fn

        return _fn(self._api, router_key, username)

    def list_users(self, router_key: str, limit: int = 50) -> RouterOSResponse:
        """Return up to limit hotspot users from the router."""
        all_users = self._get_all_users_cached(router_key)
        return all_users[:limit] if all_users else []

    def get_user(self, router_key: str, user_id: str) -> RouterOSRow | None:
        """Return a single hotspot user dict by its .id, or None if not found."""
        all_users = self._get_all_users_cached(router_key)
        for user in all_users:
            if user.get(".id") == user_id:
                return user
        return None

    def _get_leases_by_mac(self, router_key: str, macs: set[str]) -> dict[str, RouterOSRow]:
        """Fetch DHCP leases and return a dict keyed by lower-case MAC address."""
        leases = self._api.execute(router_key, "ip/dhcp-server/lease/print")
        return {
            str(lease.get("mac-address", "")).lower(): lease
            for lease in leases
            if str(lease.get("mac-address", "")).lower() in macs
        }

    def get_profiles(self, router_key: str) -> list[RouterOSRow]:
        """Return list of hotspot user profiles from the router."""
        from typing import cast

        cached = self._profiles_cache.get(router_key)
        if cached is not None:
            return cast(list[RouterOSRow], cached)
        try:
            results = self._api.execute(router_key, "ip/hotspot/user/profile/print")
            self._profiles_cache.set(router_key, results)
            return results
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Failed to fetch hotspot profiles in get_profiles (router='%s') "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )
            return []
        except Exception as e:  # noqa: BLE001
            logger.exception(
                "Failed to fetch hotspot profiles in get_profiles (router='%s') "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return []

    def _prepare_card_users(
        self,
        count: int,
        length: int,
        card_system: CardSystem,
        profile: str,
        prefix: str,
        limit_uptime: str,
        limit_bytes: str,
        batch_comment: str,
        existing_names: set[str],
    ) -> list[tuple[CardData, dict[str, str]]]:
        """Generate unique credentials and build API params for card users."""
        prepared_users: list[tuple[CardData, dict[str, str]]] = []
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

                card_item = CardData(
                    username=username,
                    password=password,
                    card_number=i,
                    profile=profile,
                    limit_uptime=limit_uptime,
                    limit_bytes=limit_bytes,
                    comment=batch_comment,
                )
                user_params: dict[str, str] = {
                    "name": username,
                    "profile": profile,
                    "comment": batch_comment,
                }
                if password:
                    user_params["password"] = password
                if limit_bytes:
                    user_params["limit-bytes-total"] = limit_bytes
                if limit_uptime:
                    user_params["limit-uptime"] = limit_uptime

                prepared_users.append((card_item, user_params))
            except ValueError as e:
                logger.error(
                    "Card preparation error at index %d in _prepare_card_users: %s",
                    i, e,
                    exc_info=True,
                )
                break
        return prepared_users

    def _get_card_creation_lock(self, router_key: str) -> threading.Lock:
        with self._card_lock_lock:
            if router_key not in self._card_creation_locks:
                self._card_creation_locks[router_key] = threading.Lock()
            return self._card_creation_locks[router_key]

    def create_cards(
        self,
        router_key: str,
        count: int,
        length: int,
        card_system: CardSystem,
        profile: str,
        prefix: str = "",
        limit_uptime: str = "",
        limit_bytes: str = "",
    ) -> list[CardData]:
        """Create multiple hotspot users with optimized chunked batch insertion."""
        lock = self._get_card_creation_lock(router_key)
        with lock:
            cards: list[CardData] = []
            base_time = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            batch_comment = f"{prefix}_{base_time}" if prefix else base_time

            existing_names = self._get_existing_usernames(router_key)
            prepared_users = self._prepare_card_users(
                count,
                length,
                card_system,
                profile,
                prefix,
                limit_uptime,
                limit_bytes,
                batch_comment,
                existing_names,
            )

            chunk_size = 50
            for idx in range(0, len(prepared_users), chunk_size):
                chunk = prepared_users[idx : idx + chunk_size]
                for card_item, user_params in chunk:
                    try:
                        self._api.execute(router_key, "ip/hotspot/user/add", **user_params)
                        cards.append(card_item)
                    except (TrapError, ConnectionError, OSError) as e:
                        logger.error(
                            "Failed to add hotspot card user '%s' in generate_cards (router='%s') "
                            "(error type: %s): %s",
                            card_item.username, router_key,
                            type(e).__name__, sanitize_log_data(str(e)),
                            exc_info=True,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.exception(
                            "Failed to add hotspot card user '%s' in generate_cards (router='%s') "
                            "(error type: %s): %s",
                            card_item.username, router_key,
                            type(e).__name__, sanitize_log_data(str(e)),
                        )

            self.invalidate_users_cache(router_key)
            logger.info(
                "Created %d/%d hotspot cards on %s in batch", len(cards), count, router_key
            )
            return cards

    def _parse_reset_day(self, comment: str) -> int | None:
        """Extract the reset day (1-31) from a hotspot user comment.

        Delegates to ``core.hotspot_stats.parse_reset_day``.
        """
        from core.hotspot_stats import parse_reset_day

        return parse_reset_day(comment)

    def get_hotspot_stats(self, router_key: str, day: int | None = None) -> RouterOSRow | None:
        """Return hotspot statistics, optionally filtered to a single reset day.

        Delegates to ``core.hotspot_stats.get_hotspot_stats``.
        """
        from core.hotspot_stats import get_hotspot_stats as _build

        result = _build(self._api, router_key, day)
        return cast(RouterOSRow, result) if result is not None else None

    def build_usage_report(self, router_key: str, top_n: int = 15) -> RouterOSRow:
        """Build an exportable Hotspot usage report for a router.

        Delegates to ``core.hotspot_stats.build_usage_report``.
        """
        from core.hotspot_stats import build_usage_report as _build

        return cast(RouterOSRow, _build(self._api, router_key, top_n))

    def block_mac(self, router_key: str, mac: str, comment: str = "blocked by bot") -> bool:
        """يضيف MAC إلى address-list باسم hotspot_blocked.

        Delegates to ``core.hotspot_blocking.block_mac``.
        """
        from core.hotspot_blocking import block_mac as _fn

        return _fn(self._api, router_key, mac, comment)

    def unblock_mac(self, router_key: str, mac: str) -> bool:
        """يحذف MAC من address-list=hotspot_blocked.

        Delegates to ``core.hotspot_blocking.unblock_mac``.
        """
        from core.hotspot_blocking import unblock_mac as _fn

        return _fn(self._api, router_key, mac)

    def get_blocked_macs(self, router_key: str) -> list[RouterOSRow]:
        """يُعيد قائمة MACs في address-list=hotspot_blocked.

        Delegates to ``core.hotspot_blocking.get_blocked_macs``.
        """
        from core.hotspot_blocking import get_blocked_macs as _fn

        return _fn(self._api, router_key)

    def get_expiring_users(self, router_key: str, days: int = 3) -> list[RouterOSRow]:
        """إعادة قائمة المستخدمين الذين ستنتهي صلاحيتهم خلال `days` أيام.

        Delegates to ``core.hotspot_expiry.get_expiring_users``.
        """
        from core.hotspot_expiry import get_expiring_users as _fn

        return _fn(self._api, router_key, days)

    def purge_expired_users(self, router_key: str, chunk_size: int = 500) -> int:
        """
        Delete expired or exhausted users in bulk and return the count.
        Processes users in chunks to avoid timeout on large user lists.
        """
        try:
            all_users = self._api.execute_long(
                router_key,
                "ip/hotspot/user/print",
                **{".proplist": ".id,bytes-out,bytes-in,limit-bytes-total,uptime,limit-uptime"},
            )
            purged = 0
            for start in range(0, len(all_users), chunk_size):
                chunk = all_users[start : start + chunk_size]
                for u in chunk:
                    uid = str(u.get(".id", ""))
                    if not uid:
                        continue
                    limit_bytes = int(u.get("limit-bytes-total", 0) or 0)
                    bytes_used = (
                        int(u.get("bytes-out", 0) or 0) + int(u.get("bytes-in", 0) or 0)
                    )

                    limit_up_sec = _parse_uptime_seconds(str(u.get("limit-uptime", "")))
                    uptime_sec = _parse_uptime_seconds(str(u.get("uptime", "")))

                    is_bytes_expired = limit_bytes > 0 and bytes_used >= limit_bytes
                    is_uptime_expired = limit_up_sec > 0 and uptime_sec >= limit_up_sec

                    if is_bytes_expired or is_uptime_expired:
                        try:
                            self.delete_user(router_key, uid)
                            purged += 1
                        except (TrapError, ConnectionError, OSError) as ex:
                            logger.warning(
                                "Failed to purge user %s in purge_expired_users (router='%s') "
                                "(error type: %s): %s",
                                uid, router_key,
                                type(ex).__name__, sanitize_log_data(str(ex)),
                                exc_info=True,
                            )
                        except Exception as ex:  # noqa: BLE001
                            logger.warning(
                                "Failed to purge user %s in purge_expired_users (router='%s') "
                                "(error type: %s): %s",
                                uid, router_key,
                                type(ex).__name__, sanitize_log_data(str(ex)),
                                exc_info=True,
                            )
            return purged
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Failed to purge expired users on %s in purge_expired_users "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )
            return 0
        except Exception as e:  # noqa: BLE001
            logger.exception(
                "Failed to purge expired users on %s in purge_expired_users "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return 0


hotspot_manager = HotspotManager()
