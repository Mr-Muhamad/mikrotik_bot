import logging
import secrets
import string
from datetime import datetime
from core.card_models import CardSystem
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient

_CARD_TYPE_MAP = {
    "type1": CardSystem.DIFFERENT_CREDENTIALS,
    "type2": CardSystem.SAME_CREDENTIALS,
    "type3": CardSystem.EMPTY_PASSWORD,
}

# Markers for field-level rejections from RouterOS (profile/password/etc.)
# reused from the defensive restore logic in core/backup/userman.py.
_FIELD_REJECT_MARKERS = (
    "unknown parameter",
    "unknown property",
    "no such item",
    "expected end",
    "unknown command",
)


def _is_field_rejection(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _FIELD_REJECT_MARKERS)


logger = logging.getLogger(__name__)


class UserManager:
    """Manages User Manager card creation, listing, and random credential generation."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def _generate_digits(self, length: int) -> str:
        return "".join(secrets.choice(string.digits) for _ in range(length))

    def generate_username(self, length: int = 8) -> str:
        """Generate a random numeric username of the given length."""
        return self._generate_digits(length)

    def generate_password(self, length: int = 8) -> str:
        """Generate a random numeric password of the given length."""
        return self._generate_digits(length)

    def create_cards(self, router_key: str, count: int, card_system: CardSystem | str,
                     profile: str, username_length: int = 8, prefix: str = "") -> list[dict]:
        """Create multiple User Manager cards with the specified type and profile.

        Users are created without a ``caller-id`` binding. Use
        ``set_user_caller_id`` after creation to bind a card to a MAC address.
        """
        if isinstance(card_system, str):
            card_system = _CARD_TYPE_MAP.get(card_system)
            if card_system is None:
                return []

        cards = []
        try:
            base_path = self._api.get_userman_base_path(router_key)
            existing = {
                (u.get("name") or u.get("username") or "")
                for u in self._api.execute(
                    router_key, f"{base_path}/user/print"
                )
            }
        except Exception:
            existing = set()

        base_time = datetime.now().strftime("%Y-%m-%d_%H:%M")
        batch_comment = f"{prefix}_{base_time}" if prefix else base_time

        for i in range(count):
            try:
                for _attempt in range(10):
                    username = self._generate_digits(username_length)
                    if card_system == CardSystem.DIFFERENT_CREDENTIALS:
                        password = self._generate_digits(username_length)
                    elif card_system == CardSystem.SAME_CREDENTIALS:
                        password = username
                    else:
                        password = ""
                    if username not in existing:
                        break
                else:
                    logger.warning(f"Could not generate unique username after 10 attempts")
                    continue

                result = self._create_user(
                    router_key, username, password, profile, comment=batch_comment
                )
                cards.append(result)
                existing.add(username)
            except Exception as e:
                logger.error(f"Card {i+1}/{count} failed on {router_key}: {e}")

        logger.info(f"Created {len(cards)}/{count} cards on {router_key} (type: {card_system.name}, profile: {profile})")
        return cards

    def _create_user(self, router_key, username, password, profile, comment=""):
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
            add_params["comment"] = comment
        if not is_v7:
            add_params["shared-users"] = 1

        # Create the account first, never bundling the profile into the add call.
        self._api.execute(router_key, f"{base_path}/user/add", **add_params)

        if not profile:
            return {"username": username, "password": password,
                    "profile_linked": False, "link_error": None}

        if is_v7:
            linked, err = self._attach_v7_profile(router_key, base_path, username, profile)
        else:
            linked, err = self._attach_v6_profile(router_key, base_path, username, profile)

        return {"username": username, "password": password,
                "profile_linked": linked, "link_error": err}

    def _attach_v7_profile(self, router_key, base_path, username, profile):
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
        except Exception as e:
            logger.warning(
                f"User '{username}' was created on {router_key} but profile "
                f"'{profile}' could not be linked: {e}"
            )
            return False, str(e)
        return self._verify_profile_link(router_key, base_path, username, profile)

    def _attach_v6_profile(self, router_key, base_path, username, profile):
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
        except Exception as e:
            logger.warning(
                f"User '{username}' was created on {router_key} but profile "
                f"'{profile}' could not be activated: {e}"
            )
            return False, str(e)
        return self._verify_profile_link(router_key, base_path, username, profile)

    def _verify_profile_link(self, router_key, base_path, username, profile):
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
        except Exception as e:
            logger.warning(
                f"Could not verify profile link for '{username}' on {router_key}: {e}"
            )
            return False, f"verify failed: {e}"


    def set_user_caller_id(self, router_key: str, username: str, caller_id: str) -> None:
        """Set caller-id on an existing User Manager user after creation."""
        base_path = self._api.get_userman_base_path(router_key)
        params = {"numbers": username}
        if caller_id:
            params["caller-id"] = caller_id
        self._api.execute(router_key, f"{base_path}/user/set", **params)
        logger.info(f"Set caller-id '{caller_id}' for user '{username}' on {router_key}")

    def list_users(self, router_key: str, limit: int = 50) -> list[dict]:
        """Return up to limit User Manager users from the router.

        Handles both v6 (``username`` attribute) and v7 (``name`` attribute) so
        callers receive a normalized ``name`` key.
        """
        base_path = self._api.get_userman_base_path(router_key)
        results = self._api.execute(router_key, f"{base_path}/user/print")
        normalized = []
        for user in results:
            entry = dict(user)
            if "name" not in entry and "username" in entry:
                entry["name"] = entry["username"]
            normalized.append(entry)
        return normalized[:limit]

    def format_card(self, card: dict, index: int) -> str:
        """Format a card dict into a display string with index number."""
        lines = [
            f"🎫 كارت #{index + 1}",
            f"👤 اسم المستخدم: {card['username']}",
            f"🔑 كلمة السر: {card['password'] if card['password'] else '(فارغة)'}",
        ]
        return "\n".join(lines)

userman_manager = UserManager()