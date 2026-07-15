"""Tests for core.stats.StatsManager."""
from unittest.mock import MagicMock

from core.stats import StatsManager


class TestStatsManagerHotspot:
    def setup_method(self):
        self.manager = StatsManager()
        self.router_key = "discovered_1"

    def test_get_hotspot_stats_aggregates_counts(self):
        from core.mikrotik_api import mikrotik_api

        all_users = [
            {"name": "u1", "bytes-in": "1000", "bytes-out": "2000"},
            {"name": "u2", "bytes-in": "500", "bytes-out": "1500"},
        ]
        active_users = [{"name": "u1"}]
        mikrotik_api.execute = MagicMock(side_effect=[all_users, active_users])

        result = self.manager.get_hotspot_stats(self.router_key)

        assert result is not None
        assert result["total_users"] == 2
        assert result["active_users"] == 1
        assert result["inactive_users"] == 1
        assert result["total_bytes"] == 5000

    def test_get_hotspot_stats_handles_missing_bytes(self):
        from core.mikrotik_api import mikrotik_api

        all_users = [{"name": "u1"}]
        active_users = []
        mikrotik_api.execute = MagicMock(side_effect=[all_users, active_users])

        result = self.manager.get_hotspot_stats(self.router_key)

        assert result["total_bytes"] == 0

    def test_get_hotspot_stats_returns_none_on_exception(self):
        from core.mikrotik_api import mikrotik_api

        mikrotik_api.execute = MagicMock(side_effect=Exception("net down"))

        result = self.manager.get_hotspot_stats(self.router_key)

        assert result is None


class TestStatsManagerUserman:
    def setup_method(self):
        self.manager = StatsManager()
        self.router_key = "discovered_1"

    def test_get_userman_stats_counts_enabled_disabled(self):
        from core.mikrotik_api import mikrotik_api

        users = [
            {"name": "u1", "enabled": "true"},
            {"name": "u2", "enabled": "true"},
            {"name": "u3", "enabled": "false"},
        ]
        mikrotik_api.execute = MagicMock(return_value=users)
        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")

        result = self.manager.get_userman_stats(self.router_key)

        assert result["total_users"] == 3
        assert result["enabled_users"] == 2
        assert result["disabled_users"] == 1

    def test_get_userman_stats_handles_v6_path(self):
        from core.mikrotik_api import mikrotik_api

        mikrotik_api.execute = MagicMock(return_value=[])
        mikrotik_api.get_userman_base_path = MagicMock(return_value="tool/user-manager")

        result = self.manager.get_userman_stats(self.router_key)

        assert result["total_users"] == 0
        assert result["enabled_users"] == 0
        assert result["disabled_users"] == 0

    def test_get_userman_stats_returns_none_on_exception(self):
        from core.mikrotik_api import mikrotik_api

        mikrotik_api.execute = MagicMock(side_effect=Exception("timeout"))

        result = self.manager.get_userman_stats(self.router_key)

        assert result is None


class TestStatsManagerFormatting:
    def setup_method(self):
        self.manager = StatsManager()

    def test_format_hotspot_stats_gigabytes(self):
        stats = {
            "total_users": 5,
            "active_users": 3,
            "inactive_users": 2,
            "total_bytes": 2_500_000_000,
        }
        result = self.manager.format_hotspot_stats(stats, "Router1")
        assert "Router1" in result
        assert "2.50 GB" in result
        assert "5" in result

    def test_format_hotspot_stats_megabytes(self):
        stats = {
            "total_users": 1,
            "active_users": 1,
            "inactive_users": 0,
            "total_bytes": 5_000_000,
        }
        result = self.manager.format_hotspot_stats(stats, "R2")
        assert "5.00 MB" in result

    def test_format_hotspot_stats_kilobytes(self):
        stats = {
            "total_users": 1,
            "active_users": 0,
            "inactive_users": 1,
            "total_bytes": 1500,
        }
        result = self.manager.format_hotspot_stats(stats, "R3")
        assert "1.50 KB" in result

    def test_format_hotspot_stats_none(self):
        result = self.manager.format_hotspot_stats(None, "X")
        assert "❌" in result

    def test_format_userman_stats(self):
        stats = {"total_users": 10, "enabled_users": 7, "disabled_users": 3}
        result = self.manager.format_userman_stats(stats, "R4")
        assert "10" in result
        assert "7" in result
        assert "3" in result

    def test_format_userman_stats_none(self):
        result = self.manager.format_userman_stats(None, "X")
        assert "❌" in result
