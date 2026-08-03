"""Extended tests for core/watchdog.py — cover record_check_result branches,
load_status_from_db, clear_alert_sent, get_router_status_detail error paths,
and check_router_health edge cases."""

from datetime import datetime
from unittest.mock import patch

import pytest

from core.watchdog import (
    ALERT_NONE,
    ALERT_RECOVERED,
    ALERT_WENT_OFFLINE,
    _last_known_status,  # type: ignore[reportPrivateUsage]
    _router_status,  # type: ignore[reportPrivateUsage]
    check_router_health,
    clear_alert_sent,
    get_router_status_detail,
    load_status_from_db,
    record_check_result,
)


@pytest.fixture(autouse=True)
def _reset():  # type: ignore[reportUnusedFunction]
    _router_status.clear()
    _last_known_status.clear()
    yield
    _router_status.clear()
    _last_known_status.clear()


class TestRecordCheckResultBranches:
    def test_went_offline_when_already_sent_returns_none(self):
        _router_status["r1"] = {"alert_sent": True}
        _last_known_status["r1"] = True
        result = record_check_result("r1", False)
        assert result == ALERT_NONE

    def test_stays_offline_returns_none(self):
        _last_known_status["r1"] = False
        result = record_check_result("r1", False)
        assert result == ALERT_NONE

    def test_stays_online_returns_none(self):
        _last_known_status["r1"] = True
        _router_status["r1"] = {"alert_sent": False}
        result = record_check_result("r1", True)
        assert result == ALERT_NONE

    def test_recovered_when_not_in_status(self):
        _last_known_status["r1"] = False
        result = record_check_result("r1", True)
        assert result == ALERT_RECOVERED

    def test_recovered_resets_alert_sent(self):
        _router_status["r1"] = {"alert_sent": True}
        _last_known_status["r1"] = False
        record_check_result("r1", True)
        assert _router_status["r1"]["alert_sent"] is False

    def test_went_offline_first_time(self):
        _last_known_status["r1"] = True
        result = record_check_result("r1", False)
        assert result == ALERT_WENT_OFFLINE
        assert _router_status["r1"]["alert_sent"] is True


class TestCheckRouterHealthExtended:
    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_successful_with_cpu_and_memory(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = [
            {"cpu-load": "15", "free-memory": "52428800"}
        ]
        result = check_router_health("r1")
        assert result["online"] is True
        assert result["cpu_load"] == 15
        assert result["free_memory"] == 52428800
        mock_rh.assert_called_once_with("r1", "online")

    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_cpu_load_value_error_falls_back(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = [
            {"cpu-load": "bad", "free-memory": "also-bad"}
        ]
        result = check_router_health("r1")
        assert result["online"] is True
        assert result["cpu_load"] is None
        assert result["free_memory"] is None

    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_librouteros_error(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        from librouteros.exceptions import LibRouterosError

        mock_api.execute.side_effect = LibRouterosError("auth failed")
        result = check_router_health("r1")
        assert result["online"] is False
        assert "auth failed" in result["error"]  # type: ignore[reportOperatorIssue]
        mock_rh.assert_called_once_with("r1", "offline", "auth failed")

    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_os_error(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        mock_api.execute.side_effect = OSError("Network unreachable")
        result = check_router_health("r1")
        assert result["online"] is False

    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_empty_response(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = []
        result = check_router_health("r1")
        assert result["online"] is True
        assert result["cpu_load"] is None

    @patch("core.watchdog.record_health")
    @patch("core.watchdog.mikrotik_api")
    def test_none_response(self, mock_api, mock_rh):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = None
        result = check_router_health("r1")
        assert result["online"] is True


class TestClearAlertSent:
    def test_clears_existing(self):
        _router_status["r1"] = {"alert_sent": True}
        clear_alert_sent("r1")
        assert _router_status["r1"]["alert_sent"] is False

    def test_no_error_on_missing_key(self):
        clear_alert_sent("unknown")


class TestGetRouterStatusDetailExtended:
    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_has_active_version_exception(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        from librouteros.exceptions import LibRouterosError

        mock_api.has_active_connection.return_value = True
        mock_api.get_version.side_effect = LibRouterosError("fail")
        mock_stats.get_hotspot_stats.return_value = {"active_users": 5}
        _router_status["r1"] = {"last_ok": datetime.now().isoformat()}
        detail = get_router_status_detail("r1")
        assert detail["online"] is True
        assert detail["version"] is None
        assert detail["active_users"] == 5

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_has_active_stats_exception(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = True
        mock_api.get_version.return_value = "7.15"
        mock_stats.get_hotspot_stats.side_effect = ConnectionError("timeout")
        _router_status["r1"] = {"last_ok": datetime.now().isoformat()}
        detail = get_router_status_detail("r1")
        assert detail["version"] == "7.15"
        assert detail["active_users"] is None

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_has_active_with_last_fail_newer(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = True
        mock_api.get_version.return_value = "7.15"
        mock_stats.get_hotspot_stats.return_value = None
        _router_status["r1"] = {
            "last_ok": "2024-01-01T10:00:00",
            "last_fail": "2024-01-01T12:00:00",
        }
        detail = get_router_status_detail("r1")
        assert detail["online"] is True
        assert detail["active_users"] is None

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_has_active_get_version_os_error(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = True
        mock_api.get_version.side_effect = OSError("network")
        mock_stats.get_hotspot_stats.return_value = {"active_users": 3}
        _router_status["r1"] = {"last_ok": datetime.now().isoformat()}
        detail = get_router_status_detail("r1")
        assert detail["version"] is None
        assert detail["active_users"] == 3

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_has_active_get_stats_connection_error(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = True
        mock_api.get_version.return_value = "7.15"
        mock_stats.get_hotspot_stats.side_effect = OSError("fail")
        _router_status["r1"] = {"last_ok": datetime.now().isoformat()}
        detail = get_router_status_detail("r1")
        assert detail["active_users"] is None


class TestLoadStatusFromDb:
    @patch("core.watchdog.get_all_latest_health")
    def test_loads_online_router(self, mock_health):  # type: ignore[reportMissingParameterType]
        mock_health.return_value = {
            "r1": {"status": "online", "checked_at": "2024-06-15 10:30:00"}
        }
        load_status_from_db()
        assert _last_known_status["r1"] is True
        assert "last_ok" in _router_status["r1"]
        assert _router_status["r1"]["alert_sent"] is False

    @patch("core.watchdog.get_all_latest_health")
    def test_loads_offline_router(self, mock_health):  # type: ignore[reportMissingParameterType]
        mock_health.return_value = {
            "r1": {"status": "offline", "checked_at": "2024-06-15 10:30:00"}
        }
        load_status_from_db()
        assert _last_known_status["r1"] is False
        assert "last_fail" in _router_status["r1"]

    @patch("core.watchdog.get_all_latest_health")
    def test_handles_bad_datetime(self, mock_health):  # type: ignore[reportMissingParameterType]
        mock_health.return_value = {
            "r1": {"status": "online", "checked_at": "not-a-date"}
        }
        load_status_from_db()
        assert _last_known_status["r1"] is True
        assert "last_ok" not in _router_status["r1"]

    @patch("core.watchdog.get_all_latest_health")
    def test_handles_none_checked_at(self, mock_health):  # type: ignore[reportMissingParameterType]
        mock_health.return_value = {
            "r1": {"status": "online", "checked_at": None}
        }
        load_status_from_db()
        assert _last_known_status["r1"] is True

    @patch("core.watchdog.get_all_latest_health", side_effect=Exception("db fail"))
    def test_handles_exception_gracefully(self, mock_health):  # type: ignore[reportMissingParameterType]
        load_status_from_db()
        assert len(_router_status) == 0
