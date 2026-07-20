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
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def _get_all_users_cached(self, router_key: str) -> list[dict]:
        from typing import cast

        cached = self._users_cache.get(router_key)
        if cached is not None:
            return cast(list[dict], cached)
        # نجلب الأسماء فقط لتسريع التحقق من التكرار عند إنشاء الكروت
        users = self._api.execute(
            router_key, "ip/hotspot/user/print", **{".proplist": "name"}
        )
        self._users_cache.set(router_key, users)
        return cast(list[dict], users)

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
            users = self._api.execute(
                router_key,
                "ip/hotspot/user/print",
                **{"?name": name, ".proplist": ".id"},
            )
            return len(users) > 0
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error(f"Failed to check user existence for '{name}': {e}")
            return False

    def _generate_unique_username(
        self, prefix: str, length: int, existing_names: set
    ) -> str:
        """Generate a unique username that doesn't exist on the router."""
        max_attempts = 100
        for _ in range(max_attempts):
            random_num = self._generate_random_number(length)
            username = f"{prefix}{random_num}" if prefix else random_num
            if username not in existing_names:
                return username
        raise ValueError(
            f"Failed to generate unique username after {max_attempts} attempts"
        )

    def add_user(
        self,
        router_key: str,
        name: str,
        password: str,
        profile: str,
        bytes_total: str = "",
        uptime: str = "",
        comment: str = "",
    ) -> list[dict]:
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
                batch = self._api.execute(
                    router_key,
                    "ip/hotspot/user/print",
                    **{
                        f"?{field}": f"*{search}*",
                        ".proplist": ".id,name,profile,limit-uptime,limit-bytes-total,comment,bytes-in,bytes-out,uptime,password",
                    },
                )
                for user in batch:
                    uid = user.get(".id")
                    if uid and uid not in seen:
                        seen.add(uid)
                        results.append(user)
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.debug(
                    "API-side filtered search for '%s' on %s failed: %s",
                    search,
                    field,
                    e,
                )

        if not results:
            all_users = self._get_all_users_cached(router_key)
            for user in all_users:
                name = str(user.get("name", "")).lower()
                comment = str(user.get("comment", "")).lower()
                if search in name or search in comment:
                    results.append(user)

        return results

    def search_hosts(self, router_key: str, search_term: str) -> list[dict]:
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
        from typing import cast

        cached = self._profiles_cache.get(router_key)
        if cached is not None:
            return cast(list[dict], cached)
        try:
            results = self._api.execute(router_key, "ip/hotspot/user/profile/print")
            self._profiles_cache.set(router_key, results)
            return cast(list[dict], results)
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.error("Failed to fetch hotspot profiles: %s", e)
            return []

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
        """Create multiple hotspot users with random numbers and duplicate checking."""
        cards = []
        base_time = datetime.now().strftime("%Y-%m-%d_%H:%M")
        batch_comment = f"{prefix}_{base_time}" if prefix else base_time

        existing_names = self._get_existing_usernames(router_key)

        for i in range(1, count + 1):
            try:
                username = self._generate_unique_username(
                    prefix, length, existing_names
                )
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
                import time

                time.sleep(0.05)
                cards.append(
                    CardData(
                        username=username,
                        password=password,
                        card_number=i,
                        profile=profile,
                        limit_uptime=limit_uptime,
                        limit_bytes=limit_bytes,
                        comment=batch_comment,
                    )
                )
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.error(f"Failed to create card user at index {i}: {e}")

        self.invalidate_users_cache(router_key)
        return cards

    def format_user(self, user: dict) -> str:
        """Format a hotspot user dict into a human-readable Arabic string."""
        bytes_in = user.get("bytes-in", "0")
        bytes_out = user.get("bytes-out", "0")
        try:
            total_consumed = int(bytes_in) + int(bytes_out)
            total_text = format_bytes(str(total_consumed))
        except (ValueError, TypeError):
            total_text = "غير معروف"

        uptime_raw = user.get("limit-uptime", "")
        uptime_text = uptime_raw if uptime_raw else "غير محدود"

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
        return "\n".join(lines)

    def _parse_reset_day(self, comment: str) -> int | None:
        """Extract the reset day (1-31) from a hotspot user comment.

        Delegates to ``core.hotspot_stats.parse_reset_day``.
        """
        from core.hotspot_stats import parse_reset_day

        return parse_reset_day(comment)

    def get_hotspot_stats(self, router_key: str, day: int | None = None) -> dict | None:
        """Return hotspot statistics, optionally filtered to a single reset day.

        Delegates to ``core.hotspot_stats.get_hotspot_stats``.
        """
        from core.hotspot_stats import get_hotspot_stats as _build

        return _build(self._api, router_key, day)

    def build_usage_report(self, router_key: str, top_n: int = 15) -> dict:
        """Build an exportable Hotspot usage report for a router.

        Delegates to ``core.hotspot_stats.build_usage_report``.
        """
        from core.hotspot_stats import build_usage_report as _build

        return _build(self._api, router_key, top_n)

    def block_mac(
        self, router_key: str, mac: str, comment: str = "blocked by bot"
    ) -> bool:
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

    def get_blocked_macs(self, router_key: str) -> list[dict]:
        """يُعيد قائمة MACs في address-list=hotspot_blocked.

        Delegates to ``core.hotspot_blocking.get_blocked_macs``.
        """
        from core.hotspot_blocking import get_blocked_macs as _fn

        return _fn(self._api, router_key)

    def get_expiring_users(self, router_key: str, days: int = 3) -> list[dict]:
        """إعادة قائمة المستخدمين الذين ستنتهي صلاحيتهم خلال `days` أيام.

        Delegates to ``core.hotspot_expiry.get_expiring_users``.
        """
        from core.hotspot_expiry import get_expiring_users as _fn

        return _fn(self._api, router_key, days)


hotspot_manager = HotspotManager()
