"""Tests for core.hotspot_expiry – uptime parsing, expiry detection, and renewal-day logic."""

from __future__ import annotations

import datetime as _dt
from unittest.mock import MagicMock, patch

from core.hotspot_expiry import (
    _parse_uptime_to_seconds,
    get_custom_expiring_users,
    get_expiring_users,
    parse_renewal_day_from_comment,
)


def _freeze_today(day: int):
    """Context manager that patches datetime.datetime.now().day inside the function."""
    fake = MagicMock(wraps=_dt.datetime)
    fake_now = MagicMock()
    fake_now.day = day
    fake.now = MagicMock(return_value=fake_now)
    return patch("datetime.datetime", fake)


# ---------------------------------------------------------------------------
# _parse_uptime_to_seconds
# ---------------------------------------------------------------------------

class TestParseUptimeToSeconds:
    def test_empty_string(self):
        assert _parse_uptime_to_seconds("") == 0

    def test_none(self):
        assert _parse_uptime_to_seconds(None) == 0

    def test_zero_string(self):
        assert _parse_uptime_to_seconds("0") == 0

    def test_zero_seconds(self):
        assert _parse_uptime_to_seconds("0s") == 0

    def test_time_only(self):
        assert _parse_uptime_to_seconds("02:30:00") == 2 * 3600 + 30 * 60

    def test_time_only_minutes_seconds(self):
        assert _parse_uptime_to_seconds("00:30:00") == 30 * 60

    def test_time_only_seconds_only(self):
        assert _parse_uptime_to_seconds("00:00:45") == 45

    def test_days_and_time(self):
        assert _parse_uptime_to_seconds("1d02:30:00") == 86400 + 2 * 3600 + 30 * 60

    def test_multiple_days(self):
        assert _parse_uptime_to_seconds("3d00:00:00") == 3 * 86400

    def test_large_days(self):
        assert _parse_uptime_to_seconds("30d00:00:00") == 30 * 86400

    def test_days_with_minutes_only(self):
        assert _parse_uptime_to_seconds("1d00:15:00") == 86400 + 15 * 60

    def test_malformed_returns_zero(self):
        assert _parse_uptime_to_seconds("garbage") == 0

    def test_partial_garbage_returns_zero(self):
        assert _parse_uptime_to_seconds("abc123") == 0

    def test_random_string_returns_zero(self):
        assert _parse_uptime_to_seconds("xyz") == 0

    def test_numbers_only_returns_zero(self):
        assert _parse_uptime_to_seconds("12345") == 0

    def test_zero_days_zero_time(self):
        assert _parse_uptime_to_seconds("0d00:00:00") == 0

    def test_non_string_coercion(self):
        assert _parse_uptime_to_seconds("1d01:00:00") == 86400 + 3600


# ---------------------------------------------------------------------------
# get_expiring_users
# ---------------------------------------------------------------------------

def _make_user(name: str, profile: str = "default", limit_uptime: str = "3d00:00:00", disabled: str = "false") -> dict:
    return {"name": name, "profile": profile, "limit-uptime": limit_uptime, "disabled": disabled}


def _make_active(user: str, uptime: str = "1d00:00:00") -> dict:
    return {"user": user, "uptime": uptime}


class TestGetExpiringUsers:
    def _api(self, users=None, active=None):
        api = MagicMock()
        calls = {}
        calls["user"] = users if users is not None else []
        calls["active"] = active if active is not None else []
        call_count = {"n": 0}

        def execute(router_key, path, **kwargs):
            call_count["n"] += 1
            if "user/print" in path:
                return calls["user"]
            return calls["active"]

        api.execute = MagicMock(side_effect=execute)
        return api

    def test_empty_users(self):
        api = self._api(users=[], active=[])
        assert get_expiring_users(api, "rk") == []

    def test_disabled_user_skipped(self):
        api = self._api(
            users=[_make_user("u1", disabled="true", limit_uptime="1d00:00:00")],
            active=[],
        )
        assert get_expiring_users(api, "rk") == []

    def test_zero_limit_uptime_skipped(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="0")],
            active=[],
        )
        assert get_expiring_users(api, "rk") == []

    def test_empty_limit_uptime_skipped(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="")],
            active=[],
        )
        assert get_expiring_users(api, "rk") == []

    def test_user_within_window(self):
        # 3 day limit, no active sessions → 3 remaining days ≤ 3 → included
        api = self._api(
            users=[_make_user("u1", limit_uptime="3d00:00:00")],
            active=[],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1
        assert result[0]["name"] == "u1"
        assert result[0]["remaining_days"] <= 3

    def test_user_outside_window(self):
        # 10 day limit, no active → 10 remaining > 3 → excluded
        api = self._api(
            users=[_make_user("u1", limit_uptime="10d00:00:00")],
            active=[],
        )
        assert get_expiring_users(api, "rk", days=3) == []

    def test_active_session_reduces_remaining(self):
        # 3d limit, 2d used → 1d remaining
        api = self._api(
            users=[_make_user("u1", limit_uptime="3d00:00:00")],
            active=[_make_active("u1", "2d00:00:00")],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1
        assert result[0]["remaining_days"] == round(1 * 86400 / 86400, 1)

    def test_multiple_active_sessions_aggregated(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="3d00:00:00")],
            active=[
                _make_active("u1", "1d00:00:00"),
                _make_active("u1", "0d12:00:00"),
            ],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1
        # used = 36h, limit = 72h, remaining = 36h = 1.5 days
        assert result[0]["remaining_days"] == round(1.5, 1)

    def test_used_exceeds_limit_clamped_to_zero(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="1d00:00:00")],
            active=[_make_active("u1", "5d00:00:00")],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1
        assert result[0]["remaining_days"] == 0

    def test_sorted_by_remaining_days(self):
        api = self._api(
            users=[
                _make_user("u2", limit_uptime="3d00:00:00"),
                _make_user("u1", limit_uptime="1d00:00:00"),
            ],
            active=[],
        )
        result = get_expiring_users(api, "rk", days=3)
        names = [r["name"] for r in result]
        assert names == ["u1", "u2"]

    def test_active_fetch_failure_graceful(self):
        api = MagicMock()

        def execute(router_key, path, **kwargs):
            if "user/print" in path:
                return [_make_user("u1", limit_uptime="1d00:00:00")]
            raise ConnectionError("boom")

        api.execute = MagicMock(side_effect=execute)
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1

    def test_librouteros_error(self):
        from librouteros.exceptions import LibRouterosError

        api = MagicMock()
        api.execute.side_effect = LibRouterosError("fail")
        assert get_expiring_users(api, "rk") == []

    def test_connection_error(self):
        api = MagicMock()
        api.execute.side_effect = ConnectionError("timeout")
        assert get_expiring_users(api, "rk") == []

    def test_os_error(self):
        api = MagicMock()
        api.execute.side_effect = OSError("network")
        assert get_expiring_users(api, "rk") == []

    def test_profile_in_output(self):
        api = self._api(
            users=[_make_user("u1", profile="gold", limit_uptime="1d00:00:00")],
            active=[],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert result[0]["profile"] == "gold"

    def test_uptime_limit_raw_preserved(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="2d05:30:00")],
            active=[],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert result[0]["uptime_limit"] == "2d05:30:00"

    def test_disabled_false_string_not_skipped(self):
        api = self._api(
            users=[_make_user("u1", disabled="false", limit_uptime="1d00:00:00")],
            active=[],
        )
        result = get_expiring_users(api, "rk", days=3)
        assert len(result) == 1

    def test_default_days_param(self):
        api = self._api(
            users=[_make_user("u1", limit_uptime="4d00:00:00")],
            active=[],
        )
        # Default days=3, 4d remaining > 3 → excluded
        assert get_expiring_users(api, "rk") == []
        # Explicit days=5 → included
        result = get_expiring_users(api, "rk", days=5)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# parse_renewal_day_from_comment
# ---------------------------------------------------------------------------

class TestParseRenewalDayFromComment:
    def test_empty_string(self):
        assert parse_renewal_day_from_comment("") == ("", None)

    def test_none_like_empty(self):
        assert parse_renewal_day_from_comment("") == ("", None)

    def test_slash_comment(self):
        name, day = parse_renewal_day_from_comment("user/22")
        assert name == "user"
        assert day == 22

    def test_dash_comment(self):
        name, day = parse_renewal_day_from_comment("أحمد-15")
        assert name == "أحمد"
        assert day == 15

    def test_slash_with_space(self):
        name, day = parse_renewal_day_from_comment("john / 5")
        assert name == "john"
        assert day == 5

    def test_dash_with_space(self):
        name, day = parse_renewal_day_from_comment("ali - 10")
        assert name == "ali"
        assert day == 10

    def test_no_number(self):
        name, day = parse_renewal_day_from_comment("just a name")
        assert name == "just a name"
        assert day is None

    def test_number_too_large(self):
        name, day = parse_renewal_day_from_comment("user/32")
        assert name == "user/32"
        assert day is None

    def test_number_zero(self):
        name, day = parse_renewal_day_from_comment("user/0")
        assert name == "user/0"
        assert day is None

    def test_number_one_valid(self):
        name, day = parse_renewal_day_from_comment("user/1")
        assert name == "user"
        assert day == 1

    def test_number_31_valid(self):
        name, day = parse_renewal_day_from_comment("user/31")
        assert name == "user"
        assert day == 31

    def test_number_99_invalid(self):
        name, day = parse_renewal_day_from_comment("user/99")
        assert name == "user/99"
        assert day is None

    def test_leading_trailing_whitespace(self):
        name, day = parse_renewal_day_from_comment("  user/22  ")
        assert name == "user"
        assert day == 22

    def test_only_slash_number(self):
        name, day = parse_renewal_day_from_comment("/10")
        assert day == 10
        # name_part is empty, falls back to full comment
        assert name == "/10"

    def test_comment_without_separator(self):
        name, day = parse_renewal_day_from_comment("hello123")
        assert name == "hello123"
        assert day is None

    def test_multiple_slashes_first_taken(self):
        name, day = parse_renewal_day_from_comment("a/b/5")
        assert day == 5

    def test_arabic_name_with_dash(self):
        name, day = parse_renewal_day_from_comment("محمد-8")
        assert name == "محمد"
        assert day == 8

    def test_single_digit_day(self):
        name, day = parse_renewal_day_from_comment("user/3")
        assert name == "user"
        assert day == 3

    def test_two_digit_day(self):
        name, day = parse_renewal_day_from_comment("user/28")
        assert name == "user"
        assert day == 28


# ---------------------------------------------------------------------------
# get_custom_expiring_users
# ---------------------------------------------------------------------------

def _make_custom_user(name: str, profile: str = "default", comment: str = "", disabled: str = "false") -> dict:
    return {"name": name, "profile": profile, "comment": comment, "disabled": disabled}


class TestGetCustomExpiringUsers:
    def _api(self, users=None):
        api = MagicMock()
        api.execute.return_value = users if users is not None else []
        return api

    def test_empty_users(self):
        api = self._api([])
        assert get_custom_expiring_users(api, "rk") == []

    def test_disabled_user_skipped(self):
        api = self._api([_make_custom_user("u1", comment="alice/10", disabled="true")])
        assert get_custom_expiring_users(api, "rk") == []

    def test_no_renewal_day_skipped(self):
        api = self._api([_make_custom_user("u1", comment="no number here")])
        assert get_custom_expiring_users(api, "rk") == []

    def test_empty_comment_skipped(self):
        api = self._api([_make_custom_user("u1", comment="")])
        assert get_custom_expiring_users(api, "rk") == []

    def test_user_expiring_today(self):
        with _freeze_today(10):
            api = self._api([_make_custom_user("u1", comment="alice/10")])
            result = get_custom_expiring_users(api, "rk", days_window=3)
            assert len(result) == 1
            assert result[0]["days_left"] == 0
            assert result[0]["renewal_day"] == 10

    def test_user_expiring_in_2_days(self):
        with _freeze_today(8):
            api = self._api([_make_custom_user("u1", comment="alice/10")])
            result = get_custom_expiring_users(api, "rk", days_window=3)
            assert len(result) == 1
            assert result[0]["days_left"] == 2

    def test_user_outside_window(self):
        with _freeze_today(1):
            api = self._api([_make_custom_user("u1", comment="alice/10")])
            # 10 - 1 = 9 days > 3 window → excluded
            assert get_custom_expiring_users(api, "rk", days_window=3) == []

    def test_renewal_wraps_around_month(self):
        with _freeze_today(29):
            # renewal_day=2 is 3 days away (29→30→31→1→2 = 3 days in 30-day month logic)
            # days_left = 30 - 29 + 2 = 3
            api = self._api([_make_custom_user("u1", comment="alice/2")])
            result = get_custom_expiring_users(api, "rk", days_window=3)
            assert len(result) == 1
            assert result[0]["days_left"] == 3

    def test_renewal_wrap_outside_window(self):
        with _freeze_today(25):
            # renewal_day=2 → days_left = 30 - 25 + 2 = 7 > 3
            api = self._api([_make_custom_user("u1", comment="alice/2")])
            assert get_custom_expiring_users(api, "rk", days_window=3) == []

    def test_sorted_by_days_left(self):
        with _freeze_today(10):
            api = self._api([
                _make_custom_user("u2", comment="bob/12"),
                _make_custom_user("u1", comment="alice/11"),
                _make_custom_user("u3", comment="carol/10"),
            ])
            result = get_custom_expiring_users(api, "rk", days_window=5)
            days = [r["days_left"] for r in result]
            assert days == sorted(days)

    def test_display_name_from_comment(self):
        with _freeze_today(10):
            api = self._api([_make_custom_user("u1", comment="فاطمة/12")])
            result = get_custom_expiring_users(api, "rk", days_window=5)
            assert result[0]["display_name"] == "فاطمة"

    def test_display_name_fallback_to_username(self):
        with _freeze_today(10):
            # /12 → parse_renewal_day_from_comment returns clean_name="/12" (full comment)
            # which is truthy, so display_name = "/12" (not username fallback)
            api = self._api([_make_custom_user("u1", comment="/12")])
            result = get_custom_expiring_users(api, "rk", days_window=5)
            assert result[0]["display_name"] == "/12"

    def test_api_exception_handled(self):
        with _freeze_today(10):
            api = MagicMock()
            api.execute.side_effect = Exception("unexpected")
            assert get_custom_expiring_users(api, "rk") == []

    def test_profile_in_output(self):
        with _freeze_today(5):
            api = self._api([_make_custom_user("u1", profile="premium", comment="alice/7")])
            result = get_custom_expiring_users(api, "rk", days_window=3)
            assert result[0]["profile"] == "premium"

    def test_username_in_output(self):
        with _freeze_today(5):
            api = self._api([_make_custom_user("u1", comment="alice/7")])
            result = get_custom_expiring_users(api, "rk", days_window=3)
            assert result[0]["username"] == "u1"

    def test_days_window_param(self):
        with _freeze_today(10):
            api = self._api([_make_custom_user("u1", comment="alice/14")])
            # 14 - 10 = 4 days, window=3 → excluded
            assert get_custom_expiring_users(api, "rk", days_window=3) == []
            # window=5 → included
            result = get_custom_expiring_users(api, "rk", days_window=5)
            assert len(result) == 1

    def test_dash_separator(self):
        with _freeze_today(10):
            api = self._api([_make_custom_user("u1", comment="alice-12")])
            result = get_custom_expiring_users(api, "rk", days_window=5)
            assert len(result) == 1
            assert result[0]["display_name"] == "alice"
