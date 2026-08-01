import logging

from librouteros.exceptions import TrapError

from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient
from utils.formatters import sanitize_log_data

logger = logging.getLogger(__name__)


class ProfileSync:
    """Fetches User Manager profile names from a MikroTik router."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def get_userman_profiles(self, router_key: str) -> list[str]:
        """Return a list of User Manager profile names from the router."""
        try:
            base_path = self._api.get_userman_base_path(router_key)
            results = self._api.execute(router_key, f"{base_path}/profile/print")
            return [str(r.get("name", "")) for r in results if r.get("name")]
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Error fetching user manager profiles in get_userman_profiles (router='%s') "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
                exc_info=True,
            )
            return []
        except Exception as e:  # noqa: BLE001 - catch-all: log unexpected error before returning result
            logger.exception(
                "Error fetching user manager profiles in get_userman_profiles (router='%s') "
                "(error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return []


profile_sync = ProfileSync()
