"""Complete mock for MikrotikAPI — no real RouterOS connections."""

from typing import Any

from tests.fixtures.hotspot_users import (
    SAMPLE_DHCP_LEASES,
    SAMPLE_HOTSPOT_HOSTS,
    SAMPLE_HOTSPOT_PROFILES,
    SAMPLE_HOTSPOT_USERS,
)


class MikrotikAPIMock:
    """In-memory mock that mimics MikrotikAPI behaviour.

    Stores users/profiles/hosts in lists so CRUD operations affect real state.
    Tracks all executed commands for test assertions.
    """

    def __init__(self):
        self._users: list[dict] = [dict(u) for u in SAMPLE_HOTSPOT_USERS]
        self._profiles: list[dict] = [dict(p) for p in SAMPLE_HOTSPOT_PROFILES]
        self._hosts: list[dict] = [dict(h) for h in SAMPLE_HOTSPOT_HOSTS]
        self._leases: list[dict] = [dict(lease) for lease in SAMPLE_DHCP_LEASES]
        self.commands_executed: list[tuple[str, str, dict]] = []
        self.last_router_key: str | None = None
        self._version = "7.15"
        self._next_user_id = len(SAMPLE_HOTSPOT_USERS) + 1
        self._next_host_id = len(SAMPLE_HOTSPOT_HOSTS) + 1

    # --- public API matching MikrotikAPI ---

    def execute(self, router_key: str, command: str, **kwargs) -> list[dict]:
        self.commands_executed.append((router_key, command, kwargs))
        self.last_router_key = router_key
        return self._route_command(command, kwargs)

    def execute_long(self, router_key: str, command: str, **kwargs) -> list[dict]:
        # Heavy-command variant (backups/restores) — same in-memory behaviour.
        return self.execute(router_key, command, **kwargs)

    def execute_non_blocking(self, router_key: str, command: str, **kwargs) -> None:
        self.commands_executed.append((router_key, command, kwargs))

    def get_version(self, router_key: str = "router1") -> str:
        return self._version

    def is_version_7(self, router_key: str = "router1") -> bool:
        return self._version.startswith("7")

    def get_userman_base_path(self, router_key: str = "router1") -> str:
        return "user-manager" if self.is_version_7(router_key) else "tool/user-manager"

    def get_router_name(self, router_key: str = "router1") -> str:
        return "TestRouter"

    def invalidate_router_name(self, router_key: str) -> None:
        pass

    def check_connection_health(self, router_key: str) -> tuple[bool, str]:
        """Mock health check — always returns healthy."""
        return True, ""

    def upload_file_to_router(self, router_key: str, local_path: str, remote_name: str) -> bool:
        return True

    def download_file_from_router(self, router_key: str, remote_name: str, local_dir: str) -> bool:
        return True

    # --- internal routing ---

    def _route_command(self, command: str, kwargs: dict) -> list[dict]:
        handlers: dict[str, Any] = {
            "ip/hotspot/user/print": self._filter_users,
            "ip/hotspot/user/add": self._add_user,
            "ip/hotspot/user/set": self._apply_update,
            "ip/hotspot/user/remove": self._remove_user,
            "ip/hotspot/user/reset-counters": lambda _: [],
            "ip/hotspot/user/profile/print": lambda _: self._profiles,
            "ip/hotspot/host/print": lambda _: self._hosts,
            "ip/hotspot/host/remove": self._remove_host,
            "ip/hotspot/active/print": lambda _: [],
            "ip/dhcp-server/lease/print": lambda _: self._leases,
            "system/resource/print": lambda _: [{"version": self._version}],
            "system/identity/print": lambda _: [{"name": "TestRouter"}],
        }
        handler = handlers.get(command)
        if handler is None:
            return []
        return handler(kwargs)

    def _add_user(self, kwargs: dict) -> list[dict]:
        entry = dict(kwargs)
        if ".id" not in entry:
            entry[".id"] = f"*{self._next_user_id}"
            self._next_user_id += 1
        self._users.append(entry)
        return [dict(entry)]

    def _filter_users(self, kwargs: dict) -> list[dict]:
        if not kwargs:
            return list(self._users)
        limit = kwargs.get("limit")
        filter_kwargs = {k: v for k, v in kwargs.items() if k not in ("limit", ".proplist")}
        results = []
        for field, value in filter_kwargs.items():
            field_name = field.lstrip("?")
            pattern = str(value).lower().strip("*")
            for user in self._users:
                field_val = str(user.get(field_name, "")).lower()
                if pattern in field_val and user not in results:
                    results.append(user)
        if not filter_kwargs:
            results = list(self._users)
        if limit is not None:
            try:
                results = results[: int(limit)]
            except (ValueError, TypeError):
                pass
        return results

    def _apply_update(self, kwargs: dict) -> list[dict]:
        uid = kwargs.pop(".id", None)
        for user in self._users:
            if user.get(".id") == uid:
                user.update(kwargs)
                break
        return []

    def _remove_user(self, kwargs: dict) -> list[dict]:
        uid = kwargs.get(".id")
        self._users = [u for u in self._users if u.get(".id") != uid]
        return []

    def _remove_host(self, kwargs: dict) -> list[dict]:
        hid = kwargs.get(".id")
        self._hosts = [h for h in self._hosts if h.get(".id") != hid]
        return []

    # --- test helpers ---

    def reset(self):
        self.__init__()

    def add_user(self, user: dict):
        self._users.append(dict(user))

    def set_version(self, version: str):
        self._version = version
