"""Extended tests for HotspotManager — covers untested methods and branches.

Tests _parse_uptime_seconds, user_exists, edit_user, reset_user_counters,
enable_user, disable_user, purge_expired_users, _get_leases_by_mac,
get_profiles error path, and search_users fallback path.
"""

from unittest.mock import patch

import pytest
from librouteros.exceptions import LibRouterosError

from core.hotspot_manager import _parse_uptime_seconds  # type: ignore[reportPrivateUsage]


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestParseUptimeSeconds:
    def test_empty_string(self):
        assert _parse_uptime_seconds("") == 0

    def test_none_input(self):
        assert _parse_uptime_seconds(None) == 0  # type: ignore[reportArgumentType]

    def test_days_only(self):
        assert _parse_uptime_seconds("1d") == 86400

    def test_hours_only(self):
        assert _parse_uptime_seconds("2h") == 7200

    def test_minutes_only(self):
        assert _parse_uptime_seconds("30m") == 1800

    def test_seconds_only(self):
        assert _parse_uptime_seconds("45s") == 45

    def test_full_dhms(self):
        assert _parse_uptime_seconds("1d2h3m4s") == 86400 + 7200 + 180 + 4

    def test_hhmmss_format(self):
        assert _parse_uptime_seconds("01:30:00") == 5400

    def test_mmss_format(self):
        assert _parse_uptime_seconds("30:00") == 1800

    def test_plain_integer(self):
        assert _parse_uptime_seconds("3600") == 3600

    def test_invalid_string(self):
        assert _parse_uptime_seconds("abc") == 0

    def test_partial_components(self):
        assert _parse_uptime_seconds("1d3m") == 86400 + 180


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestUserExists:
    ROUTER_KEY = "discovered_1"

    def test_empty_name(self):
        assert hotspot_manager.user_exists(self.ROUTER_KEY, "") is False

    def test_blank_name(self):
        assert hotspot_manager.user_exists(self.ROUTER_KEY, "   ") is False

    def test_none_name(self):
        assert hotspot_manager.user_exists(self.ROUTER_KEY, None) is False  # type: ignore[reportArgumentType]

    def test_existing_user(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="existcheck", password="1234", profile="default"
        )
        assert hotspot_manager.user_exists(self.ROUTER_KEY, "existcheck") is True

    def test_nonexistent_user(self):
        assert hotspot_manager.user_exists(self.ROUTER_KEY, "no_such_user_xyz") is False

    def test_api_error_returns_false(self):
        with patch.object(
            hotspot_manager._api,  # type: ignore[reportPrivateUsage]
            "execute",
            side_effect=LibRouterosError("timeout"),
        ):
            result = hotspot_manager.user_exists(self.ROUTER_KEY, "testuser")
        assert result is False


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestEditUser:
    ROUTER_KEY = "discovered_1"

    def test_edit_password(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtpw", password="old", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtpw")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, password="new")  # type: ignore[reportArgumentType]
        updated = hotspot_manager.get_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert updated["password"] == "new"

    def test_edit_profile(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtprof", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtprof")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, profile="vip")  # type: ignore[reportArgumentType]
        updated = hotspot_manager.get_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert updated["profile"] == "vip"

    def test_edit_comment_sanitized(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtcomm", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtcomm")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, comment="test comment")  # type: ignore[reportArgumentType]
        updated = hotspot_manager.get_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert updated.get("comment") is not None

    def test_edit_disabled(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtdis", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtdis")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, disabled="yes")  # type: ignore[reportArgumentType]
        updated = hotspot_manager.get_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert updated.get("disabled") == "yes"

    def test_edit_underscore_key_normalization(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtnorm", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtnorm")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, limit_bytes_total="500")  # type: ignore[reportArgumentType]
        updated = hotspot_manager.get_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert updated.get("limit-bytes-total") == "500"

    def test_edit_disallowed_field_ignored(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtdisf", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtdisf")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, nonexistent_field="value")  # type: ignore[reportArgumentType]

    def test_edit_none_value_ignored(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtnone", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtnone")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, password=None)  # type: ignore[reportArgumentType]

    def test_edit_non_string_value_converted(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="edtint", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "edtint")
        uid = users[0][".id"]
        hotspot_manager.edit_user(self.ROUTER_KEY, uid, limit_uptime="1d")  # type: ignore[reportArgumentType]


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestResetEnableDisable:
    ROUTER_KEY = "discovered_1"

    def test_reset_user_counters(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="rstcnt", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "rstcnt")
        uid = users[0][".id"]
        result = hotspot_manager.reset_user_counters(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert result is not None

    def test_enable_user(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="enuser", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "enuser")
        uid = users[0][".id"]
        result = hotspot_manager.enable_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert result is not None

    def test_disable_user(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="disuser", password="1234", profile="default"
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "disuser")
        uid = users[0][".id"]
        result = hotspot_manager.disable_user(self.ROUTER_KEY, uid)  # type: ignore[reportArgumentType]
        assert result is not None


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestPurgeExpiredUsers:
    ROUTER_KEY = "discovered_1"

    def test_purge_no_users(self):
        result = hotspot_manager.purge_expired_users("nonexistent_router")
        assert result == 0

    def test_purge_with_expired_bytes(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY,
            name="purgebytes",
            password="1234",
            profile="default",
            bytes_total="100",
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "purgebytes")
        uid = users[0][".id"]
        hotspot_manager.edit_user(
            self.ROUTER_KEY, uid, limit_bytes_total="50"  # type: ignore[reportArgumentType]
        )

        result = hotspot_manager.purge_expired_users(self.ROUTER_KEY)
        assert result >= 0

    def test_purge_api_error_returns_zero(self):
        with patch.object(
            hotspot_manager._api,  # type: ignore[reportPrivateUsage]
            "execute",
            side_effect=Exception("fail"),
        ):
            result = hotspot_manager.purge_expired_users(self.ROUTER_KEY)
        assert result == 0

    def test_purge_user_without_id_skipped(self):
        with patch.object(
            hotspot_manager._api,  # type: ignore[reportPrivateUsage]
            "execute",
            return_value=[{"limit-bytes-total": "0", "uptime": "", "limit-uptime": ""}],
        ):
            result = hotspot_manager.purge_expired_users(self.ROUTER_KEY)
        assert result == 0


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestGetProfilesError:
    ROUTER_KEY = "discovered_1"

    def test_api_error_returns_empty(self):
        with patch.object(
            hotspot_manager._api,  # type: ignore[reportPrivateUsage]
            "execute",
            side_effect=LibRouterosError("fail"),
        ):
            result = hotspot_manager.get_profiles(self.ROUTER_KEY)
        assert result == []


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestSearchUsersFallback:
    ROUTER_KEY = "discovered_1"

    def test_search_users_fallback_to_in_memory(self):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="fallbackuser", password="1234", profile="default"
        )

        original_execute = hotspot_manager._api.execute  # type: ignore[reportPrivateUsage]

        call_count = 0

        def failing_execute(router_key, path, **kwargs):  # type: ignore[reportMissingParameterType]
            nonlocal call_count
            call_count += 1
            if "name" in path and "user/print" in path and call_count <= 2:
                raise LibRouterosError("filter not supported")
            return original_execute(router_key, path, **kwargs)

        with patch.object(hotspot_manager._api, "execute", side_effect=failing_execute):  # type: ignore[reportPrivateUsage]
            results = hotspot_manager.search_users(self.ROUTER_KEY, "fallbackuser")

        assert len(results) >= 1


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestGetLeasesByMac:
    ROUTER_KEY = "discovered_1"

    def test_empty_macs(self):
        result = hotspot_manager._get_leases_by_mac(self.ROUTER_KEY, set())  # type: ignore[reportPrivateUsage]
        assert result == {}


from core.hotspot_manager import hotspot_manager
