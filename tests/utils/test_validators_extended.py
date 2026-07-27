"""Tests for utils.validators — comprehensive coverage of all validation functions."""

import pytest

from utils.validators import (
    sanitize_comment,
    validate_bytes_input,
    validate_ip,
    validate_mac,
    validate_password,
    validate_port,
    validate_positive_int,
    validate_username,
)

# ─── sanitize_comment ─────────────────────────────────────────


class TestSanitizeComment:
    def test_empty_returns_empty(self):
        assert sanitize_comment("") == ""
        assert sanitize_comment(None) == ""

    def test_strips_control_chars(self):
        result = sanitize_comment("hello\x00\x01\x02world")
        assert result == "helloworld"

    def test_replaces_newlines(self):
        result = sanitize_comment("line1\nline2\rline3\ttab")
        assert "\n" not in result
        assert "\r" not in result
        assert "\t" not in result
        assert "line1" in result

    def test_collapses_spaces(self):
        result = sanitize_comment("hello    world")
        assert "hello world" in result

    def test_truncates_to_max_length(self):
        result = sanitize_comment("a" * 300, max_length=200)
        assert len(result) == 200

    def test_normal_comment_preserved(self):
        assert sanitize_comment("normal comment") == "normal comment"


# ─── validate_bytes_input ─────────────────────────────────────


class TestValidateBytesInput:
    def test_empty_returns_empty(self):
        assert validate_bytes_input("") == ""

    def test_valid_format(self):
        assert validate_bytes_input("1G") == "1000000000"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_bytes_input("abcX")


# ─── validate_ip ──────────────────────────────────────────────


class TestValidateIp:
    def test_empty_returns_invalid(self):
        ok, msg = validate_ip("")
        assert ok is False
        assert "مطلوب" in msg

    def test_valid_ipv4(self):
        ok, msg = validate_ip("192.168.1.1")
        assert ok is True

    def test_valid_ipv6(self):
        ok, msg = validate_ip("::1")
        assert ok is True

    def test_invalid_ip(self):
        ok, msg = validate_ip("999.999.999.999")
        assert ok is False
        assert "غير صالح" in msg

    def test_invalid_string(self):
        ok, msg = validate_ip("not-an-ip")
        assert ok is False


# ─── validate_port ────────────────────────────────────────────


class TestValidatePort:
    def test_empty_returns_invalid(self):
        ok, msg = validate_port("")
        assert ok is False
        assert "مطلوب" in msg

    def test_valid_port(self):
        ok, msg = validate_port("80")
        assert ok is True

    def test_min_port(self):
        ok, _ = validate_port("1")
        assert ok is True

    def test_max_port(self):
        ok, _ = validate_port("65535")
        assert ok is True

    def test_zero_port(self):
        ok, msg = validate_port("0")
        assert ok is False

    def test_over_max(self):
        ok, msg = validate_port("65536")
        assert ok is False

    def test_non_numeric(self):
        ok, msg = validate_port("abc")
        assert ok is False
        assert "رقماً" in msg

    def test_negative(self):
        ok, _ = validate_port("-1")
        assert ok is False


# ─── validate_username ────────────────────────────────────────


class TestValidateUsername:
    def test_empty_returns_invalid(self):
        ok, msg = validate_username("")
        assert ok is False

    def test_too_short(self):
        ok, msg = validate_username("ab")
        assert ok is False

    def test_too_long(self):
        ok, msg = validate_username("a" * 65)
        assert ok is False

    def test_valid(self):
        ok, _ = validate_username("admin123")
        assert ok is True

    def test_with_underscores(self):
        ok, _ = validate_username("user_name")
        assert ok is True

    def test_with_hyphens(self):
        ok, _ = validate_username("user-name")
        assert ok is True

    def test_with_colons(self):
        ok, _ = validate_username("user:name")
        assert ok is True

    def test_with_dots(self):
        ok, _ = validate_username("user.name")
        assert ok is True

    def test_special_chars_rejected(self):
        ok, msg = validate_username("user@name")
        assert ok is False


# ─── validate_password ────────────────────────────────────────


class TestValidatePassword:
    def test_empty_returns_invalid(self):
        ok, msg = validate_password("")
        assert ok is False
        assert "4 أحرف" in msg

    def test_too_short(self):
        ok, msg = validate_password("abc")
        assert ok is False

    def test_too_long(self):
        ok, msg = validate_password("a" * 65)
        assert ok is False

    def test_valid(self):
        ok, _ = validate_password("pass1234")
        assert ok is True

    def test_newline_rejected(self):
        ok, msg = validate_password("pass\nword")
        assert ok is False
        assert "غير مسموحة" in msg

    def test_carriage_return_rejected(self):
        ok, msg = validate_password("pass\rword")
        assert ok is False

    def test_tab_rejected(self):
        ok, msg = validate_password("pass\tword")
        assert ok is False


# ─── validate_positive_int ────────────────────────────────────


class TestValidatePositiveInt:
    def test_valid(self):
        ok, _ = validate_positive_int("42")
        assert ok is True

    def test_zero_invalid(self):
        ok, msg = validate_positive_int("0")
        assert ok is False
        assert "موجب" in msg

    def test_negative_invalid(self):
        ok, msg = validate_positive_int("-5")
        assert ok is False

    def test_non_numeric(self):
        ok, msg = validate_positive_int("abc")
        assert ok is False
        assert "صحيح" in msg


# ─── validate_mac ─────────────────────────────────────────────


class TestValidateMac:
    def test_valid_colon_separated(self):
        ok, mac = validate_mac("AA:BB:CC:DD:EE:FF")
        assert ok is True
        assert mac == "AA:BB:CC:DD:EE:FF"

    def test_valid_hyphen_separated(self):
        ok, mac = validate_mac("AA-BB-CC-DD-EE-FF")
        assert ok is True
        assert mac == "AA:BB:CC:DD:EE:FF"

    def test_valid_dot_separated(self):
        ok, mac = validate_mac("AA.BB.CC.DD.EE.FF")
        assert ok is True
        assert mac == "AA:BB:CC:DD:EE:FF"

    def test_lowercased_normalized(self):
        ok, mac = validate_mac("aa:bb:cc:dd:ee:ff")
        assert ok is True
        assert mac == "AA:BB:CC:DD:EE:FF"

    def test_empty_returns_invalid(self):
        ok, msg = validate_mac("")
        assert ok is False

    def test_whitespace_only_invalid(self):
        ok, msg = validate_mac("   ")
        assert ok is False

    def test_wrong_length(self):
        ok, msg = validate_mac("AA:BB:CC")
        assert ok is False

    def test_invalid_hex(self):
        ok, msg = validate_mac("GG:HH:II:JJ:KK:LL")
        assert ok is False
