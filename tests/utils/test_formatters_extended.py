"""Tests for utils.formatters — comprehensive coverage of all formatting functions."""

import pytest

from utils.formatters import (
    SENSITIVE_API_FIELDS,
    format_bytes,
    format_hotspot_stats,
    format_hotspot_usage_report,
    format_hotspot_user,
    format_trend_chart,
    format_user_list,
    format_userman_stats,
    format_vs_yesterday,
    parse_bytes,
    sanitize_api_response,
)

# ─── parse_bytes ──────────────────────────────────────────────


class TestParseBytes:
    def test_empty_returns_empty(self):
        assert parse_bytes("") == ""

    def test_plain_number_passthrough(self):
        assert parse_bytes("12345") == "12345"

    def test_float_passthrough(self):
        assert parse_bytes("1.5") == "1.5"

    def test_gigabyte_suffix(self):
        assert parse_bytes("1G") == "1000000000"

    def test_megabyte_suffix(self):
        assert parse_bytes("500M") == "500000000"

    def test_kilobyte_suffix(self):
        assert parse_bytes("10K") == "10000"

    def test_terabyte_suffix(self):
        assert parse_bytes("1T") == "1000000000000"

    def test_lowercase_suffix(self):
        assert parse_bytes("2g") == "2000000000"

    def test_float_suffix(self):
        assert parse_bytes("1.5G") == "1500000000"

    def test_range_format(self):
        assert parse_bytes("1G-500M") == "1000000000-500000000"

    def test_range_with_spaces(self):
        assert parse_bytes("10G - 500M") == "10000000000-500000000"

    def test_scientific_notation_rejected(self):
        with pytest.raises(ValueError, match="الصيغة العلمية"):
            parse_bytes("1e10")

    def test_scientific_uppercase(self):
        with pytest.raises(ValueError, match="الصيغة العلمية"):
            parse_bytes("1.5E-3")

    def test_single_char_raises(self):
        with pytest.raises(ValueError):
            parse_bytes("G")

    def test_invalid_suffix(self):
        with pytest.raises(ValueError, match="غير صالح"):
            parse_bytes("500X")

    def test_invalid_number_before_suffix(self):
        with pytest.raises(ValueError, match="ليست رقماً"):
            parse_bytes("abcG")


# ─── format_bytes ─────────────────────────────────────────────


class TestFormatBytes:
    def test_none_returns_unlimited(self):
        assert format_bytes(None) == "غير محدود"

    def test_empty_returns_unlimited(self):
        assert format_bytes("") == "غير محدود"

    def test_gigabytes(self):
        assert "GB" in format_bytes("1073741824")

    def test_megabytes(self):
        assert "MB" in format_bytes("5000000")

    def test_kilobytes(self):
        assert "KB" in format_bytes("5000")

    def test_bytes(self):
        assert format_bytes("500") == "500 B"

    def test_non_numeric_passthrough(self):
        assert format_bytes("abc") == "abc"

    def test_zero(self):
        assert format_bytes("0") == "0 B"


# ─── sanitize_api_response ────────────────────────────────────


class TestSanitizeApiResponse:
    def test_empty_list(self):
        assert sanitize_api_response([]) == []

    def test_none_returns_none(self):
        assert sanitize_api_response(None) is None

    def test_password_masked(self):
        result = sanitize_api_response([{"password": "secret123", "name": "admin"}])
        assert result[0]["password"] == "***"
        assert result[0]["name"] == "admin"

    def test_all_sensitive_fields(self):
        row = {field: "value" for field in SENSITIVE_API_FIELDS}
        result = sanitize_api_response([row])  # type: ignore[reportArgumentType]
        for field in SENSITIVE_API_FIELDS:
            assert result[0][field] == "***"

    def test_non_sensitive_fields_unchanged(self):
        result = sanitize_api_response([{"name": "test", "profile": "default"}])
        assert result[0]["name"] == "test"


# ─── format_user_list ─────────────────────────────────────────


class TestFormatUserList:
    def test_empty_list(self):
        result = format_user_list([])
        assert "لا يوجد مستخدمين" in result

    def test_single_user(self):
        result = format_user_list([{"name": "user1", "profile": "default", ".id": "*1"}])
        assert "1. user1 (default)" in result
        assert "*1" in result

    def test_user_with_comment(self):
        result = format_user_list([{"name": "u1", "comment": "VIP", "profile": "p"}])
        assert "VIP" in result

    def test_truncation_at_max_items(self):
        users = [{"name": f"u{i}", "profile": "p", ".id": f"*{i}"} for i in range(25)]
        result = format_user_list(users, max_items=10)  # type: ignore[reportArgumentType]
        assert "15 مستخدمين آخرين" in result

    def test_below_max_no_truncation(self):
        users = [{"name": "u1"}, {"name": "u2"}]
        result = format_user_list(users, max_items=20)  # type: ignore[reportArgumentType]
        assert "مستخدمين آخرين" not in result


# ─── format_hotspot_user ──────────────────────────────────────


class TestFormatHotspotUser:
    def test_basic_formatting(self):
        user = {
            "name": "testuser",
            "password": "pass123",
            "profile": "default",
            "bytes-in": "1000",
            "bytes-out": "2000",
            "limit-bytes-total": "1000000000",
            "limit-uptime": "1d00:00:00",
            "comment": "test comment",
            ".id": "*5",
        }
        result = format_hotspot_user(user)  # type: ignore[reportArgumentType]
        assert "testuser" in result
        assert "********" in result  # password masked
        assert "default" in result
        assert "test comment" in result
        assert "*5" in result

    def test_no_password(self):
        result = format_hotspot_user({"name": "u"})
        assert "لا يوجد" in result

    def test_invalid_bytes_returns_unknown(self):
        result = format_hotspot_user({"bytes-in": "abc", "bytes-out": "xyz"})
        assert "غير معروف" in result

    def test_empty_uptime(self):
        result = format_hotspot_user({"name": "u"})
        assert "غير محدود" in result


# ─── format_hotspot_stats ─────────────────────────────────────


class TestFormatHotspotStats:
    def test_none_returns_error(self):
        assert "خطأ" in format_hotspot_stats(None, "router1")

    def test_formats_correctly(self):
        stats = {
            "total_users": 100, "active_users": 50,
            "inactive_users": 50, "total_bytes": 5000000,
        }
        result = format_hotspot_stats(stats, "router1")  # type: ignore[reportArgumentType]
        assert "router1" in result
        assert "100" in result
        assert "50" in result


# ─── format_userman_stats ─────────────────────────────────────


class TestUsermanStats:
    def test_none_returns_error(self):
        assert "خطأ" in format_userman_stats(None, "router1")

    def test_formats_correctly(self):
        stats = {"total_users": 200, "enabled_users": 150, "disabled_users": 50}
        result = format_userman_stats(stats, "router1")  # type: ignore[reportArgumentType]
        assert "200" in result
        assert "150" in result
        assert "50" in result


# ─── format_hotspot_usage_report ──────────────────────────────


class TestFormatHotspotUsageReport:
    def test_none_returns_empty(self):
        result = format_hotspot_usage_report(None, "router1")  # type: ignore[reportArgumentType]
        assert "لا يوجد مستخدمون" in result

    def test_zero_total_returns_empty(self):
        result = format_hotspot_usage_report({"total": 0}, "router1")
        assert "لا يوجد مستخدمون" in result

    def test_full_report(self):
        report = {
            "total": 100,
            "active": 60,
            "disabled": 40,
            "with_limit": 30,
            "total_bytes_str": "5 GB",
            "near_limit": [{"name": "a"}],
            "expired": [{"name": "b"}, {"name": "c"}],
            "inactive": [],
            "top_consumers": [{"name": "top1", "total_str": "1 GB", "percent": 50.0}],
        }
        result = format_hotspot_usage_report(report, "router1")  # type: ignore[reportArgumentType]
        assert "100" in result
        assert "top1" in result
        assert "50%" in result


# ─── format_trend_chart ──────────────────────────────────────


class TestFormatTrendChart:
    def test_empty_returns_empty(self):
        assert format_trend_chart([]) == ""

    def test_single_snapshot(self):
        result = format_trend_chart([{"active_users": 10, "snapshot_date": "2025-01-15"}])
        assert "10" in result

    def test_multiple_snapshots(self):
        data = [
            {"active_users": 5, "snapshot_date": "2025-01-10"},
            {"active_users": 10, "snapshot_date": "2025-01-11"},
        ]
        result = format_trend_chart(data)  # type: ignore[reportArgumentType]
        assert "5" in result
        assert "10" in result

    def test_all_zero_uses_one_as_max(self):
        result = format_trend_chart([{"active_users": 0, "snapshot_date": "2025-01-10"}])
        assert "0" in result


# ─── format_vs_yesterday ─────────────────────────────────────


class TestFormatVsYesterday:
    def test_none_yesterday_returns_empty(self):
        current = {"active_users": 10}
        assert format_vs_yesterday(current, None) == ""  # type: ignore[reportArgumentType]

    def test_increase(self):
        result = format_vs_yesterday({"active_users": 30}, {"active_users": 25})
        assert "↑5" in result
        assert "25 → 30" in result

    def test_decrease(self):
        result = format_vs_yesterday({"active_users": 20}, {"active_users": 30})
        assert "↓10" in result

    def test_equal(self):
        result = format_vs_yesterday({"active_users": 25}, {"active_users": 25})
        assert "↔" in result
