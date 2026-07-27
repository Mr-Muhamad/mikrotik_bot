import logging

from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient

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
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"Error fetching user manager profiles "
                f"(error type: {type(e).__name__}): {e}"
            )
            return []


profile_sync = ProfileSync()
