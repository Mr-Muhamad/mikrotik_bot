"""Unit tests for database/models.py facade — operations against a temp DB."""

import pytest

from database.models import (
    BACKUP_JOBS_RETENTION_PER_ROUTER,
    cleanup_old_logs,
    delete_router,
    ensure_admin_role,
    get_admin_role,
    get_backup_schedule,
    get_db,
    get_distinct_log_actions,
    get_distinct_log_admins,
    get_distinct_log_routers,
    get_last_backup,
    get_logs,
    get_logs_count,
    get_pdf_settings,
    get_recent_backups,
    get_router_by_id,
    get_router_by_ip,
    get_router_display_name,
    get_saved_routers,
    get_user_session,
    init_db,
    list_admin_roles,
    log_action,
    record_backup_result,
    save_backup_schedule,
    save_discovered_router,
    save_user_session,
    seed_admin_roles,
    set_admin_role,
    update_pdf_settings,
    update_router_alias,
    update_router_credentials,
    update_router_identity,
)


class TestInitDB:
    def test_tables_exist_after_init(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row["name"] for row in cursor.fetchall()]
            assert "logs" in tables
            assert "pdf_settings" in tables
            assert "backup_settings" in tables
            assert "user_sessions" in tables
            assert "discovered_routers" in tables

    def test_init_db_is_idempotent(self):
        init_db()
        init_db()
        settings = get_pdf_settings()
        assert settings.get("margin_top") == 10

    def test_pdf_settings_has_default_row(self):
        settings = get_pdf_settings()
        assert settings is not None
        assert settings.get("margin_top") == 10
        assert settings.get("cards_per_row") == 4

    def test_backup_settings_has_default_row(self):
        schedule = get_backup_schedule()
        assert schedule["schedule_enabled"] is False
        assert schedule["schedule_hour"] == 3
        assert schedule["schedule_minute"] == 0


class TestLogs:
    def test_log_action_inserts_row(self):
        log_action("test_action", "testuser", "router1", 123)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs WHERE admin_id = ?", (123,))
            row = dict(cursor.fetchone())
            assert row["action"] == "test_action"
            assert row["username"] == "testuser"
            assert row["router_name"] == "router1"

    def test_cleanup_old_logs_is_opt_in(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (action, username, router_name, admin_id, timestamp) VALUES (?, ?, ?, ?, ?)",  # noqa: E501
                ("old_action", "olduser", "router1", 123, "2000-01-01 00:00:00"),
            )
            conn.commit()

        log_action("new_action", "newuser", "router1", 123)

        deleted = cleanup_old_logs(30)
        assert deleted == 1

        logs = get_logs(limit=10)
        assert [row["action"] for row in logs] == ["new_action"]

    def test_cleanup_old_logs_rejects_invalid_retention(self):
        with pytest.raises(ValueError, match="positive"):
            cleanup_old_logs(0)


class TestLogsFiltering:
    def _seed(self):
        log_action("reboot", "alice", "router1", 10)
        log_action("add_user", "bob", "router2", 20)
        log_action("reboot", "alice", "router1", 10)
        log_action("edit_user", "bob", "router2", 20)

    def test_filter_by_router(self):
        self._seed()
        rows = get_logs(filters={"router": "router1"})
        assert len(rows) == 2
        assert all(r["router_name"] == "router1" for r in rows)
        assert get_logs_count(filters={"router": "router1"}) == 2

    def test_filter_by_admin_id(self):
        self._seed()
        rows = get_logs(filters={"admin_id": 20})
        assert len(rows) == 2
        assert all(r["username"] == "bob" for r in rows)

    def test_filter_by_action(self):
        self._seed()
        rows = get_logs(filters={"action": "reboot"})
        assert len(rows) == 2
        assert all(r["action"] == "reboot" for r in rows)

    def test_filter_combined(self):
        self._seed()
        rows = get_logs(filters={"router": "router1", "action": "reboot"})
        assert len(rows) == 2
        assert all(r["router_name"] == "router1" and r["action"] == "reboot" for r in rows)
        assert get_logs_count(filters={"router": "router1", "action": "reboot"}) == 2

    def test_filter_no_match(self):
        self._seed()
        rows = get_logs(filters={"router": "ghost"})
        assert rows == []
        assert get_logs_count(filters={"router": "ghost"}) == 0

    def test_filter_by_since(self):
        self._seed()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (action, username, router_name, admin_id, timestamp) VALUES (?, ?, ?, ?, ?)",  # noqa: E501
                ("old_action", "alice", "router1", 10, "2000-01-01 00:00:00"),
            )
            conn.commit()
        rows = get_logs(filters={"since": "2001-01-01 00:00:00"})
        assert all(r["timestamp"] >= "2001-01-01 00:00:00" for r in rows)
        assert len(rows) == 4

    def test_distinct_log_actions(self):
        self._seed()
        actions = get_distinct_log_actions()
        assert set(actions) == {"reboot", "add_user", "edit_user"}

    def test_distinct_log_admins(self):
        self._seed()
        admins = get_distinct_log_admins()
        ids = {a["admin_id"] for a in admins}
        assert ids == {10, 20}

    def test_distinct_log_routers(self):
        self._seed()
        routers = get_distinct_log_routers()
        assert set(routers) == {"router1", "router2"}


class TestAdminRoles:
    def test_ensure_is_idempotent(self):
        ensure_admin_role(5001, "operator")
        ensure_admin_role(5001, "operator")
        assert get_admin_role(5001) == "operator"

    def test_get_admin_role_none_when_unset(self):
        assert get_admin_role(59999) is None

    def test_set_and_get_role(self):
        set_admin_role(5002, "viewer")
        assert get_admin_role(5002) == "viewer"
        set_admin_role(5002, "admin")
        assert get_admin_role(5002) == "admin"

    def test_set_invalid_role_raises(self):
        with pytest.raises(ValueError):
            set_admin_role(5003, "superuser")

    def test_seed_admin_roles(self):
        seed_admin_roles([5004, 5005], default_role="operator")
        assert get_admin_role(5004) == "operator"
        assert get_admin_role(5005) == "operator"

    def test_list_admin_roles_contains_seeded(self):
        seed_admin_roles([5010], default_role="admin")
        roles = list_admin_roles()
        ids = {r["admin_id"] for r in roles}
        assert 5010 in ids

    def test_default_role_is_admin_for_config_admins(self):
        from config import ADMIN_IDS

        if ADMIN_IDS:
            assert get_admin_role(ADMIN_IDS[0]) == "admin"


class TestUserSessions:
    def test_save_and_get(self):
        save_user_session(111, "router2", "add_user", '{"key": "val"}')
        session = get_user_session(111)
        assert session is not None
        assert session["selected_router"] == "router2"
        assert session["current_action"] == "add_user"
        assert session["action_data"] == '{"key": "val"}'

    def test_get_nonexistent_returns_none(self):
        assert get_user_session(99999) is None

    def test_update_existing(self):
        save_user_session(222, "old_router")
        save_user_session(222, "new_router", "new_action")
        session = get_user_session(222)
        assert session["selected_router"] == "new_router"
        assert session["current_action"] == "new_action"


class TestPDFSettings:
    def test_update_existing_column(self):
        update_pdf_settings(margin_top=25.0, cards_per_row=6)
        settings = get_pdf_settings()
        assert settings["margin_top"] == 25.0
        assert settings["cards_per_row"] == 6

    def test_update_unknown_column_raises(self):
        with pytest.raises(ValueError, match="Unknown PDF settings columns"):
            update_pdf_settings(nonexistent_col="boom")

    def test_update_partial_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown PDF settings columns"):
            update_pdf_settings(margin_top=5, fake_col="x")


class TestDiscoveredRouters:
    def test_save_and_retrieve(self):
        router_id = save_discovered_router(
            ip="10.0.0.1",
            mac="AA:BB:CC:DD:EE:FF",
            identity="TestRouter",
            version="7.15",
            board="RB750",
            port=8729,
            username="admin",
            password="secret",
        )
        assert router_id is not None

        by_id = get_router_by_id(router_id)
        assert by_id["ip_address"] == "10.0.0.1"
        assert by_id["password"] == "secret"
        assert by_id["identity"] == "TestRouter"
        assert by_id["port"] == 8729

    def test_get_router_by_ip(self):
        save_discovered_router(ip="10.0.0.2", identity="Router2")
        router = get_router_by_ip("10.0.0.2")
        assert router is not None
        assert router["identity"] == "Router2"

    def test_get_router_by_ip_not_found(self):
        assert get_router_by_ip("1.2.3.4") is None

    def test_get_router_by_id_not_found(self):
        assert get_router_by_id(9999) is None

    def test_save_updates_existing_ip(self):
        id1 = save_discovered_router(ip="10.0.0.3", identity="First")
        id2 = save_discovered_router(ip="10.0.0.3", identity="Second")
        assert id1 == id2
        router = get_router_by_id(id1)
        assert router["identity"] == "Second"

    def test_get_saved_routers_active_only(self):
        save_discovered_router(ip="10.0.0.10", identity="Active1")
        save_discovered_router(ip="10.0.0.11", identity="Active2")
        routers = get_saved_routers(active_only=True)
        ips = [r["ip_address"] for r in routers]
        assert "10.0.0.10" in ips
        assert "10.0.0.11" in ips

    def test_delete_router(self):
        router_id = save_discovered_router(ip="10.0.0.20", identity="ToDelete")
        delete_router(router_id)
        assert get_router_by_id(router_id) is None

    def test_update_credentials(self):
        router_id = save_discovered_router(ip="10.0.0.30", username="old", password="oldpass")
        update_router_credentials(router_id, "newuser", "newpass")
        router = get_router_by_id(router_id)
        assert router["username"] == "newuser"
        assert router["password"] == "newpass"

    def test_update_alias(self):
        router_id = save_discovered_router(ip="10.0.0.40", identity="SomeRouter")
        update_router_alias(router_id, "MyAlias")
        router = get_router_by_id(router_id)
        assert router["name_alias"] == "MyAlias"

    def test_update_identity(self):
        router_id = save_discovered_router(ip="10.0.0.50", identity="OldIdentity")
        update_router_identity(router_id, "NewIdentity")
        router = get_router_by_id(router_id)
        assert router["identity"] == "NewIdentity"


class TestRouterDisplayName:
    def test_alias_used_first(self):
        router = {
            "name_alias": "MyAlias",
            "identity": "SomeRouter",
            "ip_address": "1.2.3.4",
        }
        assert get_router_display_name(router) == "MyAlias"

    def test_identity_when_no_alias(self):
        router = {"name_alias": "", "identity": "MyRouter", "ip_address": "1.2.3.4"}
        assert get_router_display_name(router) == "MyRouter"

    def test_ip_when_no_identity(self):
        router = {"name_alias": "", "identity": "Unknown", "ip_address": "1.2.3.4"}
        assert get_router_display_name(router) == "1.2.3.4"

    def test_ip_when_identity_unknown(self):
        router = {"name_alias": "", "identity": "Unknown", "ip_address": "5.6.7.8"}
        assert get_router_display_name(router) == "5.6.7.8"


class TestBackupSchedule:
    def test_get_returns_defaults_for_new_db(self):
        schedule = get_backup_schedule()
        assert schedule["schedule_enabled"] is False
        assert schedule["schedule_hour"] == 3
        assert schedule["schedule_minute"] == 0

    def test_save_and_retrieve(self):
        save_backup_schedule(True, 5, 30)
        schedule = get_backup_schedule()
        assert schedule["schedule_enabled"] is True
        assert schedule["schedule_hour"] == 5
        assert schedule["schedule_minute"] == 30

    def test_disable_schedule(self):
        save_backup_schedule(True, 2, 0)
        save_backup_schedule(False, 2, 0)
        assert get_backup_schedule()["schedule_enabled"] is False

    def test_missing_backup_settings_fallback(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backup_settings WHERE id = 1")
            conn.commit()
        schedule = get_backup_schedule()
        assert schedule["schedule_enabled"] is False
        assert schedule["schedule_hour"] == 3


class TestBackupJobs:
    def test_record_and_get_last(self):
        job_id = record_backup_result("discovered_1", "full", True, "ok", router_name="R1")
        assert isinstance(job_id, int)
        last = get_last_backup("discovered_1")
        assert last is not None
        assert last["router_key"] == "discovered_1"
        assert last["backup_type"] == "full"
        assert last["status"] == "success"
        assert last["details"] == "ok"
        assert last["router_name"] == "R1"

    def test_get_last_failed_status(self):
        record_backup_result("discovered_2", "userman", False, "conn refused", router_name="R2")
        last = get_last_backup("discovered_2")
        assert last["status"] == "failed"
        assert last["backup_type"] == "userman"

    def test_get_last_returns_newest(self):
        record_backup_result("discovered_3", "full", True, "first")
        record_backup_result("discovered_3", "userman", True, "second")
        last = get_last_backup("discovered_3")
        assert last["details"] == "second"
        assert last["backup_type"] == "userman"

    def test_get_last_unknown_router_is_none(self):
        assert get_last_backup("discovered_999") is None

    def test_get_recent_backups_ordered(self):
        record_backup_result("discovered_4", "full", True, "a")
        record_backup_result("discovered_5", "userman", False, "b")
        recent = get_recent_backups(limit=10)
        assert len(recent) == 2
        assert recent[0]["details"] == "b"

    def test_get_recent_backups_respects_limit(self):
        for i in range(5):
            record_backup_result("discovered_6", "full", True, f"run{i}")
        assert len(get_recent_backups(limit=3)) == 3

    def test_retention_prunes_old_rows(self):
        for i in range(BACKUP_JOBS_RETENTION_PER_ROUTER + 5):
            record_backup_result("discovered_7", "full", True, f"run{i}")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM backup_jobs WHERE router_key = ?",
                ("discovered_7",),
            )
            count = cursor.fetchone()[0]
        assert count == BACKUP_JOBS_RETENTION_PER_ROUTER
