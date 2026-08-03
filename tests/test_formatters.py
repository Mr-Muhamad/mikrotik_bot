import unittest

from utils.formatters import (
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
    sanitize_log_data,
    sanitize_text,
)


class TestParseBytes(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(parse_bytes(""), "")

    def test_plain_number(self):
        self.assertEqual(parse_bytes("1024"), "1024")

    def test_gigabytes_suffix(self):
        result = parse_bytes("1G")
        self.assertEqual(result, "1000000000")

    def test_gigabytes_decimal(self):
        result = parse_bytes("1.5G")
        self.assertEqual(result, str(int(1.5 * 1000000000)))

    def test_megabytes_suffix(self):
        result = parse_bytes("500M")
        self.assertEqual(result, str(500 * 1000000))

    def test_kilobytes_suffix(self):
        result = parse_bytes("128K")
        self.assertEqual(result, str(128 * 1000))

    def test_range_format(self):
        result = parse_bytes("1G-500M")
        parts = result.split("-")
        self.assertEqual(len(parts), 2)
        self.assertEqual(int(parts[0]), 1000000000)
        self.assertEqual(int(parts[1]), 500 * 1000000)

    def test_scientific_notation_rejected(self):
        with self.assertRaises(ValueError):
            parse_bytes("1e3")

    def test_invalid_suffix_rejected(self):
        with self.assertRaises(ValueError):
            parse_bytes("100X")

    def test_invalid_number_rejected(self):
        with self.assertRaises(ValueError):
            parse_bytes("abcG")

    def test_range_with_plain_number_part(self):
        result = parse_bytes("500-1G")
        parts = result.split("-")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "500")

    def test_part_too_short_raises(self):
        with self.assertRaises(ValueError):
            parse_bytes("x")

    def test_terabytes_suffix(self):
        result = parse_bytes("2T")
        self.assertEqual(result, str(2 * 1000000000000))


class TestFormatBytes(unittest.TestCase):
    def test_empty_returns_unlimited(self):
        self.assertEqual(format_bytes(""), "غير محدود")

    def test_zero_returns_b(self):
        self.assertEqual(format_bytes("0"), "0 B")

    def test_bytes(self):
        self.assertEqual(format_bytes("500"), "500 B")

    def test_kilobytes(self):
        self.assertEqual(format_bytes("2000"), "2.00 KB")

    def test_megabytes(self):
        self.assertEqual(format_bytes("1000000"), "1.00 MB")

    def test_gigabytes(self):
        self.assertEqual(format_bytes("2000000000"), "2.00 GB")

    def test_invalid_input_returns_raw(self):
        self.assertEqual(format_bytes("abc"), "abc")

    def test_none_returns_unlimited(self):
        self.assertEqual(format_bytes(None), "غير محدود")


class TestFormatUserList(unittest.TestCase):
    def test_empty_returns_message(self):
        self.assertEqual(format_user_list([]), "📭 لا يوجد مستخدمين")

    def test_single_user(self):
        users = [{"name": "test", "profile": "default"}]
        result = format_user_list(users)  # type: ignore[reportArgumentType]
        self.assertIn("test", result)
        self.assertIn("default", result)

    def test_user_with_comment(self):
        users = [{"name": "test", "profile": "default", "comment": "vip"}]
        result = format_user_list(users)  # type: ignore[reportArgumentType]
        self.assertIn("vip", result)

    def test_truncation_message(self):
        users = [{"name": str(i)} for i in range(25)]
        result = format_user_list(users)  # type: ignore[reportArgumentType]
        self.assertIn("5 مستخدمين آخرين", result)

    def test_under_limit_no_truncation(self):
        users = [{"name": str(i)} for i in range(5)]
        result = format_user_list(users)  # type: ignore[reportArgumentType]
        self.assertNotIn("مستخدمين آخرين", result)


class TestFormatHotspotUser(unittest.TestCase):
    def test_full_user_fields(self):
        user = {
            "name": "testuser1",
            "password": "secret",
            "profile": "premium",
            "limit-bytes-total": "1000000000",
            "limit-uptime": "1d",
            "bytes-in": "200000000",
            "bytes-out": "100000000",
            "comment": "vip customer",
            ".id": "*1",
        }
        result = format_hotspot_user(user)  # type: ignore[reportArgumentType]
        self.assertIn("testuser1", result)
        self.assertIn("premium", result)
        self.assertIn("vip customer", result)
        self.assertIn("*1", result)
        self.assertNotIn("secret", result)
        self.assertIn("*" * 8, result)

    def test_empty_user_defaults(self):
        user = {}
        result = format_hotspot_user(user)
        self.assertIn("لا يوجد", result)
        self.assertIn("غير محدود", result)

    def test_invalid_bytes_shows_unknown(self):
        user = {"bytes-in": "abc", "bytes-out": "xyz"}
        result = format_hotspot_user(user)  # type: ignore[reportArgumentType]
        self.assertIn("غير معروف", result)


class TestSanitizeText(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(sanitize_text(""), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(sanitize_text("hello world"), "hello world")

    def test_password_value_masked(self):
        result = sanitize_text("password=secret123")
        self.assertIn("[إخفاء]", result)
        self.assertNotIn("secret123", result)

    def test_token_value_masked(self):
        result = sanitize_text("token=abc.def.ghi")
        self.assertIn("[إخفاء]", result)
        self.assertNotIn("abc.def.ghi", result)

    def test_authorization_bearer_masked(self):
        result = sanitize_text("Authorization: Bearer xyz789")
        self.assertIn("[إخفاء]", result)
        self.assertNotIn("xyz789", result)

    def test_basic_auth_masked(self):
        result = sanitize_text("Basic dXNlcjpwYXNz")
        self.assertIn("[إخفاء]", result)
        self.assertNotIn("dXNlcjpwYXNz", result)


class TestSanitizeApiResponse(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(sanitize_api_response([]), [])

    def test_sensitive_fields_masked(self):
        rows = [{"name": "test", "password": "secret", "profile": "default"}]
        result = sanitize_api_response(rows)  # type: ignore[reportArgumentType]
        self.assertEqual(result[0]["password"], "***")
        self.assertEqual(result[0]["name"], "test")
        self.assertEqual(result[0]["profile"], "default")

    def test_no_sensitive_fields_unchanged(self):
        rows = [{"name": "test", "uptime": "1d"}]
        result = sanitize_api_response(rows)  # type: ignore[reportArgumentType]
        self.assertEqual(result, rows)


class TestSanitizeLogData(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(sanitize_log_data(None))

    def test_dict_masks_sensitive_keys(self):
        data = {"username": "admin", "password": "my_pass", "ip": "1.2.3.4"}
        result = sanitize_log_data(data)
        self.assertEqual(result["username"], "admin")
        self.assertEqual(result["password"], "***")
        self.assertEqual(result["ip"], "1.2.3.4")

    def test_list_recursively_sanitized(self):
        data = [{"password": "secret"}]
        result = sanitize_log_data(data)
        self.assertEqual(result[0]["password"], "***")

    def test_string_calls_sanitize_text(self):
        result = sanitize_log_data("password=secret123")
        self.assertIn("[إخفاء]", result)
        self.assertNotIn("secret123", result)

    def test_max_depth_zero_returns_asterisks(self):
        data = {"nested": {"deep": "value"}}
        result = sanitize_log_data(data, max_depth=0)
        self.assertEqual(result, "***")

    def test_max_depth_limits_recursion(self):
        data = {"a": {"b": {"c": "value"}}}
        result = sanitize_log_data(data, max_depth=2)
        self.assertEqual(result["a"]["b"], "***")

    def test_int_float_returned_as_is(self):
        self.assertEqual(sanitize_log_data(42), 42)
        self.assertEqual(sanitize_log_data(3.14), 3.14)

    def test_tuple_returns_list(self):
        result = sanitize_log_data(("password=secret", "safe"))
        self.assertIsInstance(result, list)
        self.assertIn("[إخفاء]", str(result))

    def test_long_string_truncated(self):
        long_str = "a" * 300
        result = sanitize_log_data(long_str)
        self.assertIn("...", result)
        self.assertLessEqual(len(result), 204)


class TestFormatHotspotStats(unittest.TestCase):
    def test_empty_stats_returns_error(self):
        result = format_hotspot_stats(None, "Router1")
        self.assertIn("خطأ", result)

    def test_valid_stats(self):
        stats = {"total_users": 10, "active_users": 5, "inactive_users": 5, "total_bytes": 1000000}
        result = format_hotspot_stats(stats, "Router1")  # type: ignore[reportArgumentType]
        self.assertIn("Router1", result)
        self.assertIn("10", result)
        self.assertIn("5", result)


class TestFormatUsermanStats(unittest.TestCase):
    def test_empty_stats_returns_error(self):
        result = format_userman_stats(None, "Router1")
        self.assertIn("خطأ", result)

    def test_valid_stats(self):
        stats = {"total_users": 20, "enabled_users": 15, "disabled_users": 5}
        result = format_userman_stats(stats, "Router1")  # type: ignore[reportArgumentType]
        self.assertIn("Router1", result)
        self.assertIn("20", result)
        self.assertIn("15", result)
        self.assertIn("5", result)


class TestFormatHotspotUsageReport(unittest.TestCase):
    def test_empty_report_returns_no_users_message(self):
        result = format_hotspot_usage_report({}, "Router1")
        self.assertIn("لا يوجد مستخدمون", result)

    def test_report_with_zero_total(self):
        result = format_hotspot_usage_report({"total": 0}, "Router1")
        self.assertIn("لا يوجد مستخدمون", result)

    def test_full_report(self):
        report = {
            "total": 100,
            "active": 40,
            "disabled": 10,
            "with_limit": 50,
            "total_bytes_str": "5.00 GB",
            "near_limit": [{"name": "user1"}],
            "expired": [{"name": "user2"}],
            "inactive": [{"name": "user3"}],
            "top_consumers": [
                {"name": "heavy1", "total_str": "2.00 GB", "percent": 40.0},
            ],
        }
        result = format_hotspot_usage_report(report, "Router1")  # type: ignore[reportArgumentType]
        self.assertIn("100", result)
        self.assertIn("40", result)
        self.assertIn("heavy1", result)


class TestFormatTrendChart(unittest.TestCase):
    def test_empty_returns_empty_string(self):
        self.assertEqual(format_trend_chart([]), "")

    def test_single_snapshot(self):
        snapshots = [{"snapshot_date": "2026-07-30", "active_users": 50}]
        result = format_trend_chart(snapshots)  # type: ignore[reportArgumentType]
        self.assertIn("07-30", result)

    def test_multiple_snapshots(self):
        snapshots = [
            {"snapshot_date": "2026-07-28", "active_users": 40},
            {"snapshot_date": "2026-07-29", "active_users": 50},
            {"snapshot_date": "2026-07-30", "active_users": 30},
        ]
        result = format_trend_chart(snapshots)  # type: ignore[reportArgumentType]
        self.assertIn("07-28", result)
        self.assertIn("07-29", result)
        self.assertIn("07-30", result)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)


class TestFormatVsYesterday(unittest.TestCase):
    def test_no_yesterday_returns_empty(self):
        current = {"active_users": 30}
        self.assertEqual(format_vs_yesterday(current, None), "")  # type: ignore[reportArgumentType]

    def test_positive_diff(self):
        current = {"active_users": 30}
        yesterday = {"active_users": 25}
        result = format_vs_yesterday(current, yesterday)  # type: ignore[reportArgumentType]
        self.assertIn("↑", result)
        self.assertIn("5", result)

    def test_negative_diff(self):
        current = {"active_users": 20}
        yesterday = {"active_users": 25}
        result = format_vs_yesterday(current, yesterday)  # type: ignore[reportArgumentType]
        self.assertIn("↓", result)
        self.assertIn("5", result)

    def test_zero_diff(self):
        current = {"active_users": 25}
        yesterday = {"active_users": 25}
        result = format_vs_yesterday(current, yesterday)  # type: ignore[reportArgumentType]
        self.assertIn("↔", result)
        self.assertIn("0", result)
