"""Admin role repository.

Isolated from the former god-object ``database.models``. Imports ``get_db``,
``VALID_ROLES`` and the ``_now_utc`` helper lazily from ``database.models`` to
avoid an import cycle (models re-exports these repositories at import time).
"""

from __future__ import annotations


def ensure_admin_role(
    admin_id: int,
    default_role: str = "admin",
    changed_by: int | None = None,
) -> None:
    """Insert a role row for an admin if none exists yet (idempotent)."""
    from database.models import VALID_ROLES, get_db, now_utc

    if default_role not in VALID_ROLES:
        raise ValueError(f"invalid role: {default_role}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admin_roles (admin_id, role, changed_by, changed_at) VALUES (?, ?, ?, ?)",  # noqa: E501
            (admin_id, default_role, changed_by, now_utc()),
        )


def seed_admin_roles(admin_ids: list[int], default_role: str = "admin") -> None:
    """Ensure every configured admin has a role row (default full access)."""
    for admin_id in admin_ids:
        ensure_admin_role(admin_id, default_role)


def get_admin_role(admin_id: int) -> str | None:
    """Return the role string for an admin, or None if not recorded."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM admin_roles WHERE admin_id = ?", (admin_id,))
        row = cursor.fetchone()
        return row["role"] if row else None


def set_admin_role(admin_id: int, role: str, changed_by: int | None = None) -> None:
    """Set (insert or update) the role for an admin."""
    from database.models import VALID_ROLES, get_db, now_utc

    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO admin_roles (admin_id, role, changed_by, changed_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(admin_id) DO UPDATE SET "
            "role = excluded.role, changed_by = excluded.changed_by, changed_at = excluded.changed_at",  # noqa: E501
            (admin_id, role, changed_by, now_utc()),
        )


def list_admin_roles():
    """Return all recorded admin role rows ordered by admin_id."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT admin_id, role, changed_by, changed_at FROM admin_roles ORDER BY admin_id"
        )
        return cursor.fetchall()


def delete_admin_role(admin_id: int) -> None:
    """Delete a role for an admin."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_roles WHERE admin_id = ?", (admin_id,))
