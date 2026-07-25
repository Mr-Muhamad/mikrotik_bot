"""Abstraction (Port) for the MikroTik client.

Defines the public contract that :class:`core.mikrotik_api.MikrotikAPI`
implements and that domain managers depend on. Depending on this Protocol
instead of the concrete class enables substitution (tests, alternative
transports such as v6/v7 or a future REST client) without touching callers.

This module deliberately imports nothing from ``core`` to stay cycle-free.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias, runtime_checkable

# RouterOS API responses are loosely typed dicts; use these aliases
# instead of bare ``dict``/``list[dict]`` so pyright strict mode can
# infer proper key/value types and avoid ``Unknown`` cascades.
RouterOSRow: TypeAlias = dict[str, Any]
"""A single row returned by the RouterOS API."""

RouterOSResponse: TypeAlias = list[RouterOSRow]
"""A list of rows returned by the RouterOS API."""


@runtime_checkable
class MikrotikClient(Protocol):
    """Command execution and router-metadata contract used across the app."""

    # ── Command execution ──────────────────────────────────────
    def execute(self, router_key: str, command: str, **kwargs: object) -> RouterOSResponse: ...

    def execute_long(self, router_key: str, command: str, **kwargs: object) -> RouterOSResponse: ...

    def execute_non_blocking(self, router_key: str, command: str, **kwargs: object) -> None: ...

    # ── Router / version metadata ──────────────────────────────
    def get_router_name(self, router_key: str = ...) -> str: ...

    def get_version(self, router_key: str = ...) -> str: ...

    def get_cached_version(self, router_key: str = ...) -> str | None: ...

    def is_version_7(self, router_key: str = ...) -> bool: ...

    def get_userman_base_path(self, router_key: str = ...) -> str: ...

    def get_router_info(self, router_key: str) -> RouterOSRow: ...

    def check_connection_health(self, router_key: str) -> tuple[bool, str]: ...

    def has_active_connection(self, router_key: str) -> bool: ...

    def download_file_from_router(
        self, router_key: str, remote_name: str, local_dir: str
    ) -> bool: ...

    def upload_file_to_router(
        self, router_key: str, local_path: str, remote_name: str
    ) -> bool: ...

    # ── Cache invalidation ─────────────────────────────────────
    def invalidate_router_name(self, router_key: str) -> None: ...

    def invalidate_version(self, router_key: str) -> None: ...

    # ── Diagnostics / lifecycle ────────────────────────────────
    def get_metrics(self) -> RouterOSRow: ...

    def test_connection(
        self, ip: str, username: str, password: str, port: int = ...
    ) -> tuple[bool, str, str]: ...

    def close(self) -> None: ...
