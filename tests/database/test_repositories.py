"""Unit tests for database/repositories/* — exercised directly (not via the facade).

The ``temp_db`` fixture (tests/database/conftest.py) patches DB_PATH and the
crypto helpers so repositories can run against an isolated temp DB.
"""

import pytest

from database.repositories import (
    admin_roles,
    audit_logs,
    backups,
    card_batches,
    pdf_settings,
    routers,
    user_sessions,
)
from database.repositories.routers import get_router_display_name

# ─── routers repository ─────────────────────────────────────────


class TestRoutersRepository:
    def test_save_and_get_by_id_decrypts(self):
        router_id = routers.save_discovered_router(
            ip="10.0.0.1",
            identity="R1",
            version="7.15",
            username="admin",
            password="secret",
        )
        row = routers.get_router_by_id(router_id)
        assert row["ip_address"] == "10.0.0.1"
        assert row["password"] == "secret"  # decrypt=True default
        assert row["identity"] == "R1"

    def test_get_router_by_ip(self):
        routers.save_discovered_router(ip="10.0.0.2", identity="R2")
        assert routers.get_router_by_ip("10.0.0.2")["identity"] == "R2"
        assert routers.get_router_by_ip("1.2.3.4") is None

    def test_get_router_by_id_missing(self):
        assert routers.get_router_by_id(99999) is None

    def test_save_manual_router_encrypts_and_rejects_duplicate(self):
        router_id = routers.save_manual_router(
            ip="10.0.0.5",
            port=8728,
            username="admin",
            password="topsecret",
            alias="Edge",
        )
        row = routers.get_router_by_id(router_id)
        assert row["ip_address"] == "10.0.0.5"
        assert row["password"] == "topsecret"  # decrypted
        assert row["name_alias"] == "Edge"
        assert row["identity"] == "Unknown"
        # duplicate IP raises RouterAlreadyExistsError
        from core.exceptions import RouterAlreadyExistsError

        with pytest.raises(RouterAlreadyExistsError):
            routers.save_manual_router(ip="10.0.0.5", username="admin", password="x")

    def test_saved_routers_active_only_toggle(self):
        routers.save_discovered_router(ip="10.0.0.10", identity="A1")
        routers.save_discovered_router(ip="10.0.0.11", identity="A2")
        active = routers.get_saved_routers(active_only=True)
        assert {r["ip_address"] for r in active} == {"10.0.0.10", "10.0.0.11"}
        all_rows = routers.get_saved_routers(active_only=False)
        assert len(all_rows) == len(active)

    def test_saved_routers_decrypt_flag(self):
        routers.save_discovered_router(ip="10.0.0.20", username="u", password="p")
        encrypted = routers.get_saved_routers(active_only=True, decrypt=False)[0]
        assert encrypted["password"].startswith("enc_")
        plain = routers.get_saved_routers(active_only=True, decrypt=True)[0]
        assert plain["password"] == "p"

    def test_update_credentials_encrypts(self):
        rid = routers.save_discovered_router(ip="10.0.0.30", username="old", password="oldp")
        routers.update_router_credentials(rid, "new", "newp")
        row = routers.get_router_by_id(rid)
        assert row["username"] == "new"
        assert row["password"] == "newp"

    def test_update_last_seen_and_identity_and_alias(self):
        rid = routers.save_discovered_router(ip="10.0.0.40", identity="Old")
        routers.update_router_last_seen(rid)
        routers.update_router_identity(rid, "New")
        routers.update_router_alias(rid, "Alias")
        row = routers.get_router_by_id(rid)
        assert row["identity"] == "New"
        assert row["name_alias"] == "Alias"
        assert row["last_seen"]

    def test_delete_router(self):
        rid = routers.save_discovered_router(ip="10.0.0.50", identity="Del")
        routers.delete_router(rid)
        assert routers.get_router_by_id(rid) is None

    def test_display_name_priority(self):
        assert (
            get_router_display_name({"name_alias": "A", "identity": "I", "ip_address": "1.1.1.1"})
            == "A"
        )
        assert (
            get_router_display_name({"name_alias": "", "identity": "I", "ip_address": "1.1.1.1"})
            == "I"
        )
        assert (
            get_router_display_name(
                {"name_alias": "", "identity": "Unknown", "ip_address": "1.1.1.1"}
            )
            == "1.1.1.1"
        )


# ─── card_batches repository ───────────────────────────────────


class TestCardBatchesRepository:
    def test_save_and_get_roundtrip_decrypts(self):
        cards = [
            {"username": "u1", "password": "p1"},
            {"username": "u2", "password": "p2"},
        ]
        bid = card_batches.save_card_batch(
            router_key="discovered_1",
            name="batch1",
            batch_type="hotspot",
            profile="default",
            cards=cards,
            created_by=123,
        )
        batch = card_batches.get_card_batch(bid)
        assert batch is not None
        assert batch["name"] == "batch1"
        assert batch["count"] == 2
        assert batch["cards"] == cards  # decrypted + parsed
        assert "cards_json" not in batch

    def test_get_card_batch_missing(self):
        assert card_batches.get_card_batch(99999) is None

    def test_list_card_batches_omits_payload(self):
        card_batches.save_card_batch("discovered_1", "b", "hotspot", cards=[{"x": 1}])
        rows = card_batches.list_card_batches("discovered_1")
        assert rows
        assert all("cards_json" not in r for r in rows)

    def test_delete_card_batch(self):
        bid = card_batches.save_card_batch("discovered_1", "b", "hotspot", cards=[{"x": 1}])
        assert card_batches.delete_card_batch(bid) == 1
        assert card_batches.get_card_batch(bid) is None

    def test_decode_handles_corrupt_payload(self):
        assert card_batches._decode_batch_cards("") == []
        assert card_batches._decode_batch_cards("not-json") == []
        assert card_batches._decode_batch_cards("enc_garbage") == []


# ─── audit_logs repository ─────────────────────────────────────


class TestAuditLogsRepository:
    def test_log_and_query(self):
        audit_logs.log_action("reboot", "alice", "router1", 10)
        rows = audit_logs.get_logs(limit=10)
        assert rows[0]["action"] == "reboot"
        assert audit_logs.get_logs_count() == 1

    def test_where_clauses_bind_params_no_injection(self):
        clauses, params = audit_logs._logs_where_clauses({"router": "r'; DROP TABLE logs;--"})
        assert clauses == ["router_name = ?"]
        assert params == ["r'; DROP TABLE logs;--"]  # value is a bound param, not concatenated

    def test_distinct_and_filter(self):
        audit_logs.log_action("reboot", "alice", "r1", 10)
        audit_logs.log_action("add", "bob", "r2", 20)
        assert set(audit_logs.get_distinct_log_actions()) == {"reboot", "add"}
        assert audit_logs.get_logs(filters={"admin_id": 20})[0]["username"] == "bob"

    def test_cleanup_rejects_non_positive(self):
        with pytest.raises(ValueError, match="positive"):
            audit_logs.cleanup_old_logs(0)


# ─── admin_roles repository ────────────────────────────────────


class TestAdminRolesRepository:
    def test_ensure_idempotent(self):
        admin_roles.ensure_admin_role(5001, "operator")
        admin_roles.ensure_admin_role(5001, "operator")
        assert admin_roles.get_admin_role(5001) == "operator"

    def test_set_and_invalid(self):
        admin_roles.set_admin_role(5002, "viewer")
        assert admin_roles.get_admin_role(5002) == "viewer"
        with pytest.raises(ValueError):
            admin_roles.set_admin_role(5003, "superuser")

    def test_seed_and_list(self):
        admin_roles.seed_admin_roles([5010, 5011], default_role="admin")
        ids = {r["admin_id"] for r in admin_roles.list_admin_roles()}
        assert {5010, 5011} <= ids


# ─── user_sessions repository ──────────────────────────────────


class TestUserSessionsRepository:
    def test_save_and_get(self):
        user_sessions.save_user_session(111, "router2", "add_user", '{"k": "v"}')
        s = user_sessions.get_user_session(111)
        assert s["selected_router"] == "router2"
        assert s["current_action"] == "add_user"

    def test_missing_returns_none(self):
        assert user_sessions.get_user_session(99999) is None


# ─── pdf_settings repository ───────────────────────────────────


class TestPdfSettingsRepository:
    def test_update_and_unknown(self):
        pdf_settings.update_pdf_settings(margin_top=25.0, cards_per_row=6)
        s = pdf_settings.get_pdf_settings()
        assert s["margin_top"] == 25.0
        assert s["cards_per_row"] == 6
        with pytest.raises(ValueError, match="Unknown PDF settings columns"):
            pdf_settings.update_pdf_settings(bogus="x")


# ─── backups repository ────────────────────────────────────────


class TestBackupsRepository:
    def test_schedule_roundtrip(self):
        backups.save_backup_schedule(True, 5, 30)
        s = backups.get_backup_schedule()
        assert s["schedule_enabled"] is True
        assert s["schedule_hour"] == 5

    def test_record_and_recent(self):
        backups.record_backup_result("discovered_1", "full", True, "ok", router_name="R1")
        last = backups.get_last_backup("discovered_1")
        assert last["status"] == "success"
        assert backups.get_recent_backups(limit=5)

    def test_retention_prunes(self):
        for i in range(backups.BACKUP_JOBS_RETENTION_PER_ROUTER + 3):
            backups.record_backup_result("discovered_7", "full", True, f"run{i}")
        assert backups.get_recent_backups(limit=1000)
