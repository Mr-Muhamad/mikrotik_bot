"""Tests for database/repositories/stats_snapshots and core/stats trend methods."""

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from core.stats import StatsManager

# ─── Helper: isolated in-memory DB ──────────────────────────────────────────


def _make_get_db():
    """Return a get_db context manager backed by a fresh in-memory SQLite DB."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            router_key TEXT NOT NULL,
            snapshot_date DATE NOT NULL,
            active_users INTEGER DEFAULT 0,
            total_users INTEGER DEFAULT 0,
            bytes_in INTEGER DEFAULT 0,
            bytes_out INTEGER DEFAULT 0,
            UNIQUE(router_key, snapshot_date)
        )
    """)
    conn.commit()

    @contextmanager
    def _get_db():
        try:
            yield conn
            conn.commit()
        except Exception:  # noqa: BLE001 - catch-all: ensure rollback before re-raising
            conn.rollback()
            raise

    return _get_db


PATCH_TARGET = "database.repositories.stats_snapshots.get_db"


# ─── save_snapshot ────────────────────────────────────────────────────────


class TestSaveSnapshot:
    def test_saves_new_snapshot(self):
        from database.repositories.stats_snapshots import (
            get_week_snapshots,
            save_snapshot,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            save_snapshot("router1", {"active_users": 10, "total_users": 50})
            snaps = get_week_snapshots("router1")
        assert len(snaps) == 1
        assert snaps[0]["active_users"] == 10
        assert snaps[0]["total_users"] == 50

    def test_upsert_same_day(self):
        from database.repositories.stats_snapshots import (
            get_week_snapshots,
            save_snapshot,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            save_snapshot("router1", {"active_users": 10, "total_users": 50})
            save_snapshot("router1", {"active_users": 20, "total_users": 60})
            snaps = get_week_snapshots("router1")
        assert len(snaps) == 1
        assert snaps[0]["active_users"] == 20

    def test_multiple_routers(self):
        from database.repositories.stats_snapshots import (
            get_week_snapshots,
            save_snapshot,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            save_snapshot("router1", {"active_users": 5, "total_users": 20})
            save_snapshot("router2", {"active_users": 15, "total_users": 40})
            r1 = get_week_snapshots("router1")
            r2 = get_week_snapshots("router2")
        assert len(r1) == 1
        assert len(r2) == 1
        assert r1[0]["active_users"] == 5
        assert r2[0]["active_users"] == 15

    def test_defaults_for_missing_fields(self):
        from database.repositories.stats_snapshots import (
            get_week_snapshots,
            save_snapshot,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            save_snapshot("r1", {})
            snaps = get_week_snapshots("r1")
        assert snaps[0]["active_users"] == 0
        assert snaps[0]["bytes_in"] == 0


# ─── get_yesterday_snapshot ────────────────────────────────────────────────


class TestGetYesterdaySnapshot:
    def test_returns_none_when_empty(self):
        from database.repositories.stats_snapshots import get_yesterday_snapshot

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = get_yesterday_snapshot("router1")
        assert result is None

    def test_returns_yesterday_row(self):
        from database.repositories.stats_snapshots import get_yesterday_snapshot

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        get_db = _make_get_db()

        # أدرج بتاريخ الأمس مباشرة
        with patch(PATCH_TARGET, get_db):
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO stats_snapshots (router_key, snapshot_date, active_users, total_users) VALUES (?,?,?,?)",  # noqa: E501
                    ("r1", yesterday, 25, 100),
                )
            result = get_yesterday_snapshot("r1")

        assert result is not None
        assert result["active_users"] == 25
        assert result["snapshot_date"] == yesterday

    def test_returns_none_for_other_router(self):
        from database.repositories.stats_snapshots import (
            get_yesterday_snapshot,
            save_snapshot,
        )

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            save_snapshot("router1", {"active_users": 5})
            result = get_yesterday_snapshot("router2")
        assert result is None


# ─── get_week_snapshots ────────────────────────────────────────────────────


class TestGetWeekSnapshots:
    def test_returns_empty_list_when_no_data(self):
        from database.repositories.stats_snapshots import get_week_snapshots

        get_db = _make_get_db()
        with patch(PATCH_TARGET, get_db):
            result = get_week_snapshots("router_none")
        assert result == []

    def test_returns_snapshots_ordered_asc(self):
        from database.repositories.stats_snapshots import (
            get_week_snapshots,
        )

        get_db = _make_get_db()
        # أدرج بتواريخ متعددة
        with patch(PATCH_TARGET, get_db):
            with get_db() as conn:
                for i in range(3, 0, -1):  # 3، 2، 1 أيام مضت (نزولاً)
                    d = (date.today() - timedelta(days=i)).isoformat()
                    conn.execute(
                        "INSERT INTO stats_snapshots (router_key, snapshot_date, active_users) VALUES (?,?,?)",  # noqa: E501
                        ("r1", d, i * 10),
                    )
            snaps = get_week_snapshots("r1")

        assert len(snaps) == 3
        # مرتبة ASC — الأقدم أولاً
        assert snaps[0]["snapshot_date"] < snaps[-1]["snapshot_date"]


# ─── StatsManager trend/format methods ────────────────────────────────────


class TestStatsManagerTrend:
    def setup_method(self):
        self.sm = StatsManager(api=MagicMock())

    def test_get_week_trend_calls_repository(self):
        mock_snaps = [{"snapshot_date": "2025-01-01", "active_users": 5}]
        with patch(
            "database.repositories.stats_snapshots.get_week_snapshots",
            return_value=mock_snaps,
        ):
            result = self.sm.get_week_trend("r1")
        assert result == mock_snaps

    def test_format_trend_chart_empty(self):
        assert self.sm.format_trend_chart([]) == ""

    def test_format_trend_chart_single(self):
        snaps = [{"snapshot_date": "2025-01-15", "active_users": 8}]
        chart = self.sm.format_trend_chart(snaps)
        assert "01-15" in chart
        assert "8" in chart

    def test_format_trend_chart_bar_scaling(self):
        """Max active gets 8 blocks, zero gets 0 blocks."""
        snaps = [
            {"snapshot_date": "2025-01-01", "active_users": 0},
            {"snapshot_date": "2025-01-02", "active_users": 100},
        ]
        chart = self.sm.format_trend_chart(snaps)
        lines = chart.split("\n")
        # السطر الثاني (الأكبر) يجب أن يحتوي 8 كتل
        assert "████████" in lines[1]

    def test_format_vs_yesterday_no_yesterday(self):
        current = {"active_users": 30}
        assert self.sm.format_vs_yesterday(current, None) == ""

    def test_format_vs_yesterday_increase(self):
        current = {"active_users": 35}
        yesterday = {"active_users": 30}
        result = self.sm.format_vs_yesterday(current, yesterday)
        assert "↑5" in result
        assert "30 → 35" in result

    def test_format_vs_yesterday_decrease(self):
        current = {"active_users": 20}
        yesterday = {"active_users": 30}
        result = self.sm.format_vs_yesterday(current, yesterday)
        assert "↓10" in result

    def test_format_vs_yesterday_same(self):
        current = {"active_users": 25}
        yesterday = {"active_users": 25}
        result = self.sm.format_vs_yesterday(current, yesterday)
        assert "↔" in result
        assert "0" in result
