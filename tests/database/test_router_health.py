"""Tests for database/repositories/router_health.py — CRUD operations."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch


class TestRecordHealth:
    def test_records_online_status(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_A", "online")
        result = get_latest_health("router_A")
        assert result is not None
        assert result["status"] == "online"
        assert result["router_key"] == "router_A"

    def test_records_offline_with_error(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_B", "offline", error_msg="Connection refused")
        result = get_latest_health("router_B")
        assert result is not None
        assert result["status"] == "offline"
        assert result["error_msg"] == "Connection refused"

    def test_records_empty_error_msg(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_C", "online", error_msg="")
        result = get_latest_health("router_C")
        assert result is not None
        assert result["error_msg"] == ""

    def test_records_none_error_as_empty(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_D", "online", error_msg=None)  # type: ignore[reportArgumentType]
        result = get_latest_health("router_D")
        assert result is not None
        assert result["error_msg"] == ""

    def test_multiple_records_ordered_by_time(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_E", "online")
        record_health("router_E", "offline", error_msg="timeout")
        result = get_latest_health("router_E")
        assert result is not None
        assert result["status"] == "offline"

    def test_exception_does_not_propagate(self):
        from database.repositories.router_health import record_health

        with patch(
            "database.repositories.router_health.get_db", side_effect=RuntimeError("DB down")
        ):
            record_health("router_X", "online")


class TestGetLatestHealth:
    def test_returns_none_for_unknown_router(self):
        from database.repositories.router_health import get_latest_health

        result = get_latest_health("nonexistent")
        assert result is None

    def test_returns_dict_with_expected_keys(self):
        from database.repositories.router_health import get_latest_health, record_health

        record_health("router_F", "online")
        result = get_latest_health("router_F")
        assert result is not None
        assert set(result.keys()) == {"router_key", "status", "checked_at", "error_msg"}

    def test_exception_returns_none(self):
        from database.repositories.router_health import get_latest_health

        with patch(
            "database.repositories.router_health.get_db", side_effect=RuntimeError("fail")
        ):
            result = get_latest_health("any")
        assert result is None


class TestGetAllLatestHealth:
    def test_empty_when_no_records(self):
        from database.repositories.router_health import get_all_latest_health

        result = get_all_latest_health()
        assert result == {}

    def test_returns_one_entry_per_router(self):
        from database.repositories.router_health import get_all_latest_health, record_health

        record_health("r1", "online")
        record_health("r2", "offline")
        record_health("r1", "offline")
        result = get_all_latest_health()
        assert set(result.keys()) == {"r1", "r2"}
        assert result["r1"]["status"] == "offline"
        assert result["r2"]["status"] == "offline"

    def test_exception_returns_empty_dict(self):
        from database.repositories.router_health import get_all_latest_health

        with patch(
            "database.repositories.router_health.get_db", side_effect=RuntimeError("fail")
        ):
            result = get_all_latest_health()
        assert result == {}


class TestGetHealthHistory:
    def test_returns_empty_for_unknown(self):
        from database.repositories.router_health import get_health_history

        result = get_health_history("nonexistent")
        assert result == []

    def test_returns_records_newest_first(self):
        from database.repositories.router_health import get_health_history, record_health

        record_health("router_H", "online")
        record_health("router_H", "offline")
        record_health("router_H", "online")
        history = get_health_history("router_H")
        assert len(history) == 3
        assert history[0]["status"] == "online"
        assert history[1]["status"] == "offline"
        assert history[2]["status"] == "online"

    def test_limit_works(self):
        from database.repositories.router_health import get_health_history, record_health

        for _ in range(5):
            record_health("router_I", "online")
        history = get_health_history("router_I", limit=2)
        assert len(history) == 2

    def test_only_returns_specified_router(self):
        from database.repositories.router_health import get_health_history, record_health

        record_health("rA", "online")
        record_health("rB", "offline")
        history = get_health_history("rA")
        assert len(history) == 1
        assert history[0]["router_key"] == "rA"

    def test_exception_returns_empty(self):
        from database.repositories.router_health import get_health_history

        with patch(
            "database.repositories.router_health.get_db", side_effect=RuntimeError("fail")
        ):
            result = get_health_history("any")
        assert result == []


class TestCleanupHealthHistory:
    def test_deletes_old_records(self):
        from database.models import UTC_TIMESTAMP_FORMAT, get_db
        from database.repositories.router_health import (
            cleanup_health_history,
            get_latest_health,
            record_health,
        )

        record_health("router_old", "online")
        cutoff = datetime.now(UTC) - timedelta(days=10)
        with get_db() as conn:
            conn.execute(
                "UPDATE router_health_log SET checked_at = ? WHERE router_key = ?",
                (cutoff.strftime(UTC_TIMESTAMP_FORMAT), "router_old"),
            )
        deleted = cleanup_health_history(days=7)
        assert deleted >= 1
        assert get_latest_health("router_old") is None

    def test_keeps_recent_records(self):
        from database.repositories.router_health import (
            cleanup_health_history,
            get_latest_health,
            record_health,
        )

        record_health("router_new", "online")
        deleted = cleanup_health_history(days=7)
        assert deleted == 0
        assert get_latest_health("router_new") is not None

    def test_exception_returns_zero(self):
        from database.repositories.router_health import cleanup_health_history

        with patch(
            "database.repositories.router_health.get_db", side_effect=RuntimeError("fail")
        ):
            result = cleanup_health_history(days=7)
        assert result == 0
