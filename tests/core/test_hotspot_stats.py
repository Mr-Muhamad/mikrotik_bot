"""Tests for core/hotspot_stats.py - hotspot statistics and usage reports."""

from unittest.mock import MagicMock, patch

import pytest

from core.hotspot_stats import (
    _categorize_user,
    _classify_limit_gb,
    _safe_day,
    build_usage_report,
    get_hotspot_stats,
    parse_reset_day,
)


class TestSafeDay:
    def test_valid_day(self):
        assert _safe_day("15") == 15

    def test_boundary_min(self):
        assert _safe_day("1") == 1

    def test_boundary_max(self):
        assert _safe_day("31") == 31

    def test_out_of_range(self):
        assert _safe_day("32") is None

    def test_zero(self):
        assert _safe_day("0") is None

    def test_none(self):
        assert _safe_day(None) is None

    def test_non_numeric(self):
        assert _safe_day("abc") is None


class TestParseResetDay:
    def test_yyyy_mm_dd(self):
        assert parse_reset_day("2024-03-15") == 15

    def test_yyyy_slash_mm_dd(self):
        assert parse_reset_day("2024/03/20") == 20

    def test_dd_mm_yyyy(self):
        assert parse_reset_day("05/06/2024") == 5

    def test_dd_slash_mm(self):
        assert parse_reset_day("user 12/06") == 12

    def test_legacy_slash_dd(self):
        assert parse_reset_day("plan/25") == 25

    def test_standalone_day(self):
        assert parse_reset_day("reset on 7") == 7

    def test_empty_string(self):
        assert parse_reset_day("") is None

    def test_none_input(self):
        assert parse_reset_day(None) is None

    def test_no_match(self):
        assert parse_reset_day("no numbers here") is None


class TestClassifyLimitGb:
    def test_below_10gb(self):
        assert _classify_limit_gb(5_000_000_000) == "5.00 GB"

    def test_10gb_bucket(self):
        assert _classify_limit_gb(10_000_000_000) == "10.00 GB"

    def test_20gb_bucket(self):
        assert _classify_limit_gb(25_000_000_000) == "25.00 GB"

    def test_50gb_bucket(self):
        assert _classify_limit_gb(55_000_000_000) == "55.00 GB"

    def test_above_60gb(self):
        assert _classify_limit_gb(70_000_000_000) == "70.00 GB"


class TestCategorizeUser:
    def test_disabled_user(self):
        user = {"disabled": "true"}
        cats = {}
        active, day = _categorize_user(user, cats)
        assert active is False
        assert day is None

    def test_active_with_limit(self):
        user = {
            "disabled": "false",
            "limit-bytes-total": "10000000000",
            "comment": "15",
        }
        cats = {}
        active, day = _categorize_user(user, cats)
        assert active is True
        assert cats["10.00 GB"] == 1
        assert day == 15

    def test_active_without_limit(self):
        user = {"disabled": "false", "limit-bytes-total": "0", "comment": ""}
        cats = {}
        active, day = _categorize_user(user, cats)
        assert active is True
        assert cats["غير محدودة"] == 1
        assert day is None


class TestGetHotspotStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {
                "disabled": "false", "limit-bytes-total": "10000000000",
                "comment": "15", "name": "u1",
            },
            {"disabled": "true", "limit-bytes-total": "0", "comment": "", "name": "u2"},
        ]
        with patch("core.hotspot_stats.format_bytes", return_value="10.0 GB"):
            result = get_hotspot_stats(mock_api, "r1")
        assert result is not None
        assert result["total"] == 2
        assert result["active"] == 1
        assert result["inactive"] == 1

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        mock_api = MagicMock()
        mock_api.execute_long.side_effect = OSError("timeout")
        result = get_hotspot_stats(mock_api, "r1")
        assert result is None

    @pytest.mark.asyncio
    async def test_day_filter(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {"disabled": "false", "limit-bytes-total": "0", "comment": "10", "name": "u1"},
        ]
        with patch("core.hotspot_stats.format_bytes", return_value="0 B"):
            result = get_hotspot_stats(mock_api, "r1", day=10)
        assert result["reset_list"] != []
        assert result["selected_day"] == 10


class TestBuildUsageReport:
    @pytest.mark.asyncio
    async def test_basic_report(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {
                "name": "u1", "profile": "default", "disabled": "false",
                "bytes-in": "1000", "bytes-out": "500",
                "limit-bytes-total": "10000000", "comment": "",
            },
        ]
        with patch("core.hotspot_stats.format_bytes", side_effect=lambda s: str(s)):
            result = build_usage_report(mock_api, "r1")
        assert result["total"] == 1
        assert result["active"] == 1
        assert result["rows"][0]["total_bytes"] == 1500

    @pytest.mark.asyncio
    async def test_expired_user(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {
                "name": "u1", "profile": "p", "disabled": "false",
                "bytes-in": "5000", "bytes-out": "6000",
                "limit-bytes-total": "10000", "comment": "",
            },
        ]
        with patch("core.hotspot_stats.format_bytes", side_effect=lambda s: str(s)):
            result = build_usage_report(mock_api, "r1")
        assert len(result["expired"]) == 1

    @pytest.mark.asyncio
    async def test_disabled_user_counted(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {
                "name": "u1", "profile": "p", "disabled": "true",
                "bytes-in": "0", "bytes-out": "0",
                "limit-bytes-total": "0", "comment": "",
            },
        ]
        with patch("core.hotspot_stats.format_bytes", side_effect=lambda s: str(s)):
            result = build_usage_report(mock_api, "r1")
        assert result["disabled"] == 1
        assert len(result["inactive"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_bytes_handled(self):
        mock_api = MagicMock()
        mock_api.execute_long.return_value = [
            {
                "name": "u1", "profile": "p", "disabled": "false",
                "bytes-in": "invalid", "bytes-out": None,
                "limit-bytes-total": "0", "comment": "",
            },
        ]
        with patch("core.hotspot_stats.format_bytes", side_effect=lambda s: str(s)):
            result = build_usage_report(mock_api, "r1")
        assert result["rows"][0]["total_bytes"] == 0
