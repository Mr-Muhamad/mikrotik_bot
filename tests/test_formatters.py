import unittest

from utils.formatters import format_bytes, format_hotspot_user, format_user_list, parse_bytes


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


class TestFormatUserList(unittest.TestCase):
    def test_empty_returns_message(self):
        self.assertEqual(format_user_list([]), "📭 لا يوجد مستخدمين")

    def test_single_user(self):
        users = [{"name": "test", "profile": "default"}]
        result = format_user_list(users)
        self.assertIn("test", result)
        self.assertIn("default", result)

    def test_user_with_comment(self):
        users = [{"name": "test", "profile": "default", "comment": "vip"}]
        result = format_user_list(users)
        self.assertIn("vip", result)

    def test_truncation_message(self):
        users = [{"name": str(i)} for i in range(25)]
        result = format_user_list(users)
        self.assertIn("5 مستخدمين آخرين", result)

    def test_under_limit_no_truncation(self):
        users = [{"name": str(i)} for i in range(5)]
        result = format_user_list(users)
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
        result = format_hotspot_user(user)
        self.assertIn("testuser1", result)
        self.assertIn("premium", result)
        self.assertIn("vip customer", result)
        self.assertIn("*1", result)
        # Password masked, not leaked
        self.assertNotIn("secret", result)
        self.assertIn("*" * 8, result)

    def test_empty_user_defaults(self):
        user = {}
        result = format_hotspot_user(user)
        self.assertIn("لا يوجد", result)
        self.assertIn("غير محدود", result)

    def test_invalid_bytes_shows_unknown(self):
        user = {"bytes-in": "abc", "bytes-out": "xyz"}
        result = format_hotspot_user(user)
        self.assertIn("غير معروف", result)
