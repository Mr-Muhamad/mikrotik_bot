import logging
import secrets
import string
from datetime import datetime

from core.cache import TTLCache
from core.card_models import CardSystem
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient, RouterOSResponse, RouterOSRow
from utils.validators import sanitize_comment

_CARD_TYPE_MAP = {
    "type1": CardSystem.DIFFERENT_CREDENTIALS,
    "type2": CardSystem.SAME_CREDENTIALS,
    "type3": CardSystem.EMPTY_PASSWORD,
}

logger = logging.getLogger(__name__)


class UserManager:
    """Manages User Manager card creation, listing, and random credential generation."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api
        self._users_cache = TTLCache(max_size=20, ttl=5)
        self._sessions_cache = TTLCache(max_size=20, ttl=5)

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def _get_all_users_cached(self, router_key: str, base_path: str) -> RouterOSResponse:
        from typing import cast

        cached = self._users_cache.get(router_key)
        if cached is not None:
            return cast(RouterOSResponse, cached)
        users = self._api.execute(
            router_key,
            f"{base_path}/user/print",
            **{
                ".proplist": ".id,name,username,password,profile,disabled,shared-users,caller-id,comment"  # noqa: E501
            },
        )
        self._users_cache.set(router_key, users)
        return users

    def invalidate_users_cache(self, router_key: str):
        self._users_cache.invalidate(router_key)
        self._sessions_cache.invalidate(router_key)

    def _generate_digits(self, length: int) -> str:
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def generate_username(self, length: int = 8) -> str:
        """Generate a random numeric username of the given length."""
        return self._generate_digits(length)

    def generate_password(self, length: int = 8) -> str:
        """Generate a random numeric password of the given length."""
        return self._generate_digits(length)

    def create_cards(
        self,
        router_key: str,
        count: int,
        card_system: CardSystem | str | None,
        profile: str,
        username_length: int = 8,
        prefix: str = "",
        caller_id: str = "",
    ) -> RouterOSResponse:
        """Create multiple User Manager cards with the specified type and profile.

        Binds to caller-id directly during creation if provided.
        """
        if isinstance(card_system, str):
            card_system = _CARD_TYPE_MAP.get(card_system)
        if not isinstance(card_system, CardSystem):
            return []

        cards = []
        try:
            base_path = self._api.get_userman_base_path(router_key)
            existing = {
                (u.get("name") or u.get("username") or "")
                for u in self._api.execute(
                    router_key,
                    f"{base_path}/user/print",
                    **{".proplist": "name,username"},
                )
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Failed to fetch existing User Manager users for "
                f"deduplication on {router_key} "
                f"(error type: {type(e).__name__}): {e}"
            )
            existing = set()

        base_time = datetime.now().strftime("%Y-%m-%d_%H:%M")
        batch_comment = f"{prefix}_{base_time}" if prefix else base_time

        for i in range(count):
            try:
                for _attempt in range(10):
                    random_num = self._generate_digits(username_length)
                    username = f"{prefix}{random_num}" if prefix else random_num

                    if card_system == CardSystem.DIFFERENT_CREDENTIALS:
                        password = self._generate_digits(username_length)
                    elif card_system == CardSystem.SAME_CREDENTIALS:
                        password = username
                    else:
                        password = ""

                    if username not in existing:
                        break
                else:
                    logger.warning("Could not generate unique username after 10 attempts")
                    continue

                result = self._create_user(
                    router_key,
                    username,
                    password,
                    profile,
                    comment=batch_comment,
                    caller_id=caller_id,
                )
                cards.append(result)
                existing.add(username)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"Card {i + 1}/{count} failed on {router_key} "
                    f"(error type: {type(e).__name__}): {e}"
                )

        logger.info(
            f"Created {len(cards)}/{count} User Manager cards on {router_key} (type: {card_system.name}, profile: {profile})"  # noqa: E501
        )
        return cards

    def _create_user(
        self,
        router_key: str,
        username: str,
        password: str,
        profile: str,
        comment: str = "",
        caller_id: str = "",
    ) -> RouterOSRow:
        """Create a User Manager user and attach the selected profile.

        The user is created WITHOUT the profile first so a rejected ``profile``
        parameter can never silently discard the new account. The profile is then
        linked in a separate, version-correct step and the link is verified by a
        read-back so a silent failure can never be reported as success:
          - v7: ``user-manager/user-profile/add user=<name> profile=<profile>``
          - v6: ``tool/user-manager/user/create-and-activate-profile ...``

        Returns a dict carrying the link status so the caller can surface failures.
        """
        base_path = self._api.get_userman_base_path(router_key)
        is_v7 = not base_path.startswith("tool/")

        add_params = {"name": username}
        if password:
            add_params["password"] = password
        if comment:
            add_params["comment"] = sanitize_comment(comment)
        if caller_id:
            add_params["caller-id"] = caller_id
        if not is_v7:
            add_params["shared-users"] = "1"

        # Create the account first, never bundling the profile into the add call.
        self._api.execute(router_key, f"{base_path}/user/add", **add_params)

        if not profile:
            return {
                "username": username,
                "password": password,
                "profile_linked": False,
                "link_error": None,
            }

        if is_v7:
            linked, err = self._attach_v7_profile(router_key, base_path, username, profile)
        else:
            linked, err = self._attach_v6_profile(router_key, base_path, username, profile)

        return {
            "username": username,
            "password": password,
            "profile_linked": linked,
            "link_error": err,
        }

    def _attach_v7_profile(
        self,
        router_key: str,
        base_path: str,
        username: str,
        profile: str,
    ) -> tuple[bool, str | None]:
        """Link a profile to a v7 User Manager user via the ``user-profile`` table.

        RouterOS v7 stores the user<->profile link in a separate
        ``user-manager/user-profile`` record, not as a field on the user, so the
        correct command is ``user-profile/add user=<name> profile=<profile>``.
        A failure must not discard the already-created user; the link status is
        returned and verified by a read-back.
        """
        try:
            self._api.execute(
                router_key,
                f"{base_path}/user-profile/add",
                user=username,
                profile=profile,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"User '{username}' was created on {router_key} but profile "
                f"'{profile}' could not be linked (error type: {type(e).__name__}): {e}"
            )
            return False, str(e)
        return self._verify_profile_link(router_key, base_path, username, profile)

    def _attach_v6_profile(
        self,
        router_key: str,
        base_path: str,
        username: str,
        profile: str,
    ) -> tuple[bool, str | None]:
        """Attach and activate a profile for a v6 User Manager user.

        RouterOS v6 links the profile via the dedicated
        ``create-and-activate-profile`` command. A failure must not discard the
        already-created user; the link status is returned and verified by a
        read-back instead of being silently swallowed.
        """
        try:
            self._api.execute(
                router_key,
                f"{base_path}/user/create-and-activate-profile",
                profile=profile,
                numbers=username,
                customer="admin",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"User '{username}' was created on {router_key} but profile "
                f"'{profile}' could not be activated (error type: {type(e).__name__}): {e}"
            )
            return False, str(e)
        return self._verify_profile_link(router_key, base_path, username, profile)

    def _verify_profile_link(
        self,
        router_key: str,
        base_path: str,
        username: str,
        profile: str,
    ) -> tuple[bool, str | None]:
        """Read back the user<->profile link and confirm it was applied.

        RouterOS does not accept a query filter on ``user-profile/print``
        (it answers ``unknown parameter user``), so the link table is fetched
        and matched client-side. Returns ``(True, None)`` when a record matches,
        or ``(False, reason)`` when the link is missing so the caller can surface it.
        """
        try:
            rows = self._api.execute(router_key, f"{base_path}/user-profile/print")
            for row in rows or []:
                if row.get("profile") != profile:
                    continue
                # RouterOS returns numeric usernames as ints in this table, so
                # coerce both sides to str before comparing.
                link_user = row.get("user") or row.get("username")
                if link_user is not None and str(link_user) == str(username):
                    return True, None
            return False, "profile link not found after attach"
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Could not verify profile link for '{username}' on {router_key} "
                f"(error type: {type(e).__name__}): {e}"
            )
            return False, f"verify failed: {e}"

    def _get_user_id(self, router_key: str, username: str) -> str | None:
        """Resolve a username to its .id, handling numeric names safely."""
        base_path = self._api.get_userman_base_path(router_key)
        is_v7 = not base_path.startswith("tool/")
        field = "name" if is_v7 else "username"

        try:
            # Try API filtering first
            results = self._api.execute(
                router_key,
                f"{base_path}/user/print",
                **{ f"?{field}": username, ".proplist": ".id," + field },
            )
            for user in results or []:
                if str(user.get(field)) == str(username):
                    return str(user.get(".id", ""))
        except Exception as e:  # noqa: BLE001
            logger.debug(
                f"API filter failed in _get_user_id for {username} "
                f"(error type: {type(e).__name__}): {e}"
            )

        # Fallback to full list if filter not supported
        try:
            results = self._get_all_users_cached(router_key, base_path)
            for user in results or []:
                if str(user.get(field)) == str(username):
                    return str(user.get(".id", ""))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Error checking user by field '{field}' "
                f"(error type: {type(e).__name__}): {e}"
            )
        return None

    def set_user_caller_id(self, router_key: str, username: str, caller_id: str) -> None:
        """Set caller-id on an existing User Manager user after creation."""
        if not caller_id:
            return

        base_path = self._api.get_userman_base_path(router_key)
        uid = self._get_user_id(router_key, username)
        if not uid:
            logger.error(f"Cannot find .id for User Manager user '{username}' to set caller-id")
            return

        self._api.execute(
            router_key, f"{base_path}/user/set", **{".id": uid, "caller-id": caller_id}
        )
        logger.info(f"Set caller-id '{caller_id}' for user '{username}' on {router_key}")

    def list_users(self, router_key: str, limit: int = 50) -> RouterOSResponse:
        """Return up to limit User Manager users from the router.

        Handles both v6 (``username`` attribute) and v7 (``name`` attribute) so
        callers receive a normalized ``name`` key.
        """
        base_path = self._api.get_userman_base_path(router_key)
        results = self._get_all_users_cached(router_key, base_path)
        normalized: RouterOSResponse = []
        for user in results:
            entry = dict(user)
            if "name" not in entry and "username" in entry:
                entry["name"] = entry["username"]
            normalized.append(entry)
        return normalized[:limit]

    def search_users(self, router_key: str, search_term: str) -> RouterOSResponse:
        """Search User Manager users by name."""
        base_path = self._api.get_userman_base_path(router_key)
        is_v7 = not base_path.startswith("tool/")
        field = "name" if is_v7 else "username"

        results = self._get_all_users_cached(router_key, base_path)
        search = search_term.lower()
        matches: RouterOSResponse = []
        for user in results or []:
            name = str(user.get(field, "")).lower()
            if search in name:
                entry = dict(user)
                if "name" not in entry and "username" in entry:
                    entry["name"] = entry["username"]
                matches.append(entry)
        return matches

    def get_user(self, router_key: str, username: str) -> RouterOSRow | None:
        """Return a single User Manager user dict by name, or None if not found."""
        uid = self._get_user_id(router_key, username)
        if not uid:
            return None
        base_path = self._api.get_userman_base_path(router_key)
        results = self._api.execute(router_key, f"{base_path}/user/print", **{".id": uid})
        for user in results or []:
            if user.get(".id") == uid:
                entry = dict(user)
                if "name" not in entry and "username" in entry:
                    entry["name"] = entry["username"]
                return entry
        return None

    def add_profile_to_user(
        self, router_key: str, username: str, profile: str
    ) -> tuple[bool, str | None]:
        """Link an additional User Manager profile to an existing user.

        A User Manager user may hold multiple profiles. The link is added via
        the version-correct command and verified by a read-back so a silent
        failure is never reported as success:
          - v7: ``user-manager/user-profile/add user=<name> profile=<profile>``
          - v6: ``tool/user-manager/user/create-and-activate-profile ...``

        Returns ``(linked, error)``.
        """
        base_path = self._api.get_userman_base_path(router_key)
        is_v7 = not base_path.startswith("tool/")
        if is_v7:
            return self._attach_v7_profile(router_key, base_path, username, profile)
        return self._attach_v6_profile(router_key, base_path, username, profile)

    def delete_user(self, router_key: str, username: str) -> RouterOSResponse:
        """Delete a User Manager user by name."""
        base_path = self._api.get_userman_base_path(router_key)
        uid = self._get_user_id(router_key, username)
        if not uid:
            raise ValueError(f"User '{username}' not found")
        result = self._api.execute(router_key, f"{base_path}/user/remove", **{".id": uid})
        logger.info(f"Deleted User Manager user '{username}' on {router_key}")
        return result

    def enable_user(self, router_key: str, username: str) -> RouterOSResponse:
        """Enable a User Manager user."""
        base_path = self._api.get_userman_base_path(router_key)
        uid = self._get_user_id(router_key, username)
        if not uid:
            raise ValueError(f"User '{username}' not found")
        result = self._api.execute(router_key, f"{base_path}/user/enable", **{".id": uid})
        logger.info(f"Enabled User Manager user '{username}' on {router_key}")
        return result

    def disable_user(self, router_key: str, username: str) -> RouterOSResponse:
        """Disable a User Manager user."""
        base_path = self._api.get_userman_base_path(router_key)
        uid = self._get_user_id(router_key, username)
        if not uid:
            raise ValueError(f"User '{username}' not found")
        result = self._api.execute(router_key, f"{base_path}/user/disable", **{".id": uid})
        logger.info(f"Disabled User Manager user '{username}' on {router_key}")
        return result

    def reset_user_counters(self, router_key: str, username: str) -> RouterOSResponse:
        """Reset counters / clear profiles for a User Manager user."""
        base_path = self._api.get_userman_base_path(router_key)
        uid = self._get_user_id(router_key, username)
        if not uid:
            raise ValueError(f"User '{username}' not found")

        if base_path.startswith("tool/"):
            result = self._api.execute(
                router_key, f"{base_path}/user/clear-profiles", **{".id": uid}
            )
        else:
            result = self._api.execute(
                router_key, f"{base_path}/user/reset-counters", **{".id": uid}
            )
        logger.info(f"Reset counters for User Manager user '{username}' on {router_key}")
        return result

    def get_active_sessions(self, router_key: str) -> RouterOSResponse:
        """Return a list of active User Manager sessions."""
        base_path = self._api.get_userman_base_path(router_key)
        proplist = ".id,user,username,active,host-ip,uptime,download,upload"
        results = self._api.execute(
            router_key,
            f"{base_path}/session/print",
            **{"?active": "true", ".proplist": proplist},
        )
        # Sometimes ?active filter fails or isn't supported in some versions, fallback:
        if not results:
            results = self._api.execute(
                router_key, f"{base_path}/session/print", **{".proplist": proplist}
            )
            results = [s for s in results if str(s.get("active", "false")).lower() == "true"]

        normalized: RouterOSResponse = []
        for session in results:
            entry = dict(session)
            if "user" not in entry and "username" in entry:
                entry["user"] = entry["username"]
            normalized.append(entry)
        return normalized

    def terminate_session(self, router_key: str, session_id: str) -> RouterOSResponse:
        """Terminate a specific User Manager session by its .id or numbers."""
        base_path = self._api.get_userman_base_path(router_key)

        # v6 vs v7 remove session command
        if base_path.startswith("tool/"):
            result = self._api.execute(
                router_key, f"{base_path}/session/remove", numbers=session_id
            )
        else:
            result = self._api.execute(
                router_key, f"{base_path}/session/remove", numbers=session_id
            )

        logger.info(f"Terminated User Manager session '{session_id}' on {router_key}")
        return result

    def format_card(self, card: RouterOSRow, index: int) -> str:
        """Format a card dict into a display string with index number."""
        lines = [
            f"🎫 كارت #{index + 1}",
            f"👤 اسم المستخدم: {card['username']}",
            f"🔑 كلمة السر: {card['password'] if card['password'] else '(فارغة)'}",
        ]
        return "\n".join(lines)


userman_manager = UserManager()
