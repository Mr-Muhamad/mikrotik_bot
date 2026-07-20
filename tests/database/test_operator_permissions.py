"""Tests for database/repositories/operator_permissions and bot/router_selector.get_user_routers."""

import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

PATCH_TARGET = "database.repositories.operator_permissions.get_db"


# ─── Helper: isolated in-memory DB ──────────────────────────────────────────


def _make_get_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operator_router_permissions (
            operator_id INTEGER NOT NULL,
            router_id INTEGER NOT NULL,
            assigned_by INTEGER,
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (operator_id, router_id)
        )
    """)
    conn.commit()

    @contextmanager
    def _get_db():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return _get_db


# ─── assign_router_to_operator ────────────────────────────────────────────


class TestAssignRouter:
    def test_assign_returns_true(self):
        from database.repositories.operator_permissions import assign_router_to_operator

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = assign_router_to_operator(100, 1, 999)
        assert result is True

    def test_assign_idempotent(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            get_operator_routers,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(100, 1, 999)
            assign_router_to_operator(100, 1, 999)  # دون خطأ (INSERT OR IGNORE)
            routers = get_operator_routers(100)
        assert routers.count(1) == 1

    def test_assign_multiple_routers(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            get_operator_routers,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(100, 1, 999)
            assign_router_to_operator(100, 2, 999)
            assign_router_to_operator(100, 3, 999)
            routers = get_operator_routers(100)
        assert set(routers) == {1, 2, 3}


# ─── revoke_router_from_operator ─────────────────────────────────────────


class TestRevokeRouter:
    def test_revoke_existing_returns_true(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            revoke_router_from_operator,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(100, 1, 999)
            result = revoke_router_from_operator(100, 1)
        assert result is True

    def test_revoke_nonexistent_returns_false(self):
        from database.repositories.operator_permissions import (
            revoke_router_from_operator,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = revoke_router_from_operator(100, 99)
        assert result is False

    def test_revoke_removes_only_target(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            get_operator_routers,
            revoke_router_from_operator,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(100, 1, 999)
            assign_router_to_operator(100, 2, 999)
            revoke_router_from_operator(100, 1)
            routers = get_operator_routers(100)
        assert routers == [2]


# ─── get_operator_routers ──────────────────────────────────────────────────


class TestGetOperatorRouters:
    def test_returns_empty_for_new_operator(self):
        from database.repositories.operator_permissions import get_operator_routers

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = get_operator_routers(999)
        assert result == []

    def test_returns_list_of_ints(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            get_operator_routers,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(200, 5, 1)
            result = get_operator_routers(200)
        assert result == [5]
        assert isinstance(result[0], int)


# ─── is_operator_allowed ──────────────────────────────────────────────────


class TestIsOperatorAllowed:
    def test_allowed_after_assign(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            is_operator_allowed,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(300, 7, 1)
            result = is_operator_allowed(300, 7)
        assert result is True

    def test_not_allowed_for_unassigned(self):
        from database.repositories.operator_permissions import is_operator_allowed

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = is_operator_allowed(300, 99)
        assert result is False

    def test_not_allowed_after_revoke(self):
        from database.repositories.operator_permissions import (
            assign_router_to_operator,
            is_operator_allowed,
            revoke_router_from_operator,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            assign_router_to_operator(300, 7, 1)
            revoke_router_from_operator(300, 7)
            result = is_operator_allowed(300, 7)
        assert result is False


# ─── get_user_routers ──────────────────────────────────────────────────────


class TestGetUserRouters:
    ALL_ROUTERS = [
        {"id": 1, "identity": "R1", "ip_address": "192.168.1.1"},
        {"id": 2, "identity": "R2", "ip_address": "192.168.1.2"},
        {"id": 3, "identity": "R3", "ip_address": "192.168.1.3"},
    ]

    def test_admin_sees_all_routers(self):
        from bot.router_selector import get_user_routers

        admin_id = 12345
        with (
            patch("database.models.get_saved_routers", return_value=self.ALL_ROUTERS),
            patch("config.ADMIN_IDS", [admin_id]),
            patch("database.models.get_operator_routers", return_value=[]),
        ):
            result = get_user_routers(admin_id)
        assert len(result) == 3

    def test_customer_sees_only_owned(self):
        from bot.router_selector import get_user_routers

        customer_id = 99999
        owned_routers = [self.ALL_ROUTERS[0], self.ALL_ROUTERS[2]]
        with (
            patch("database.models.get_saved_routers", return_value=owned_routers) as mock_get,
            patch("config.ADMIN_IDS", [12345]),
        ):
            result = get_user_routers(customer_id)
        assert len(result) == 2
        mock_get.assert_called_with(active_only=True, owner_id=customer_id)

    def test_customer_with_no_routers_sees_nothing(self):
        from bot.router_selector import get_user_routers

        customer_id = 99999
        with (
            patch("database.models.get_saved_routers", return_value=[]) as mock_get,
            patch("config.ADMIN_IDS", [12345]),
        ):
            result = get_user_routers(customer_id)
        assert result == []
        mock_get.assert_called_with(active_only=True, owner_id=customer_id)
