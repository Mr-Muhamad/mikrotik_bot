"""Tests for core.watchdog module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from core.watchdog import (
    _router_status,  # type: ignore[reportPrivateUsage]
    check_router_health,
    clear_status,
    get_router_status,
    get_router_status_detail,
    mark_alert_sent,
    was_alert_sent,
)


@pytest.fixture(autouse=True)
def reset_status():
    """Reset _router_status before each test."""
    _router_status.clear()
    yield
    _router_status.clear()


class TestCheckRouterHealth:
    @patch("core.watchdog.mikrotik_api")
    def test_online_returns_true(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = [{"version": "7.12"}]
        result = check_router_health("router1")
        assert result["online"] is True
        assert result["error"] is None

    @patch("core.watchdog.mikrotik_api")
    def test_offline_returns_false(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute.side_effect = ConnectionError("Connection refused")
        result = check_router_health("router1")
        assert result["online"] is False
        assert "Connection refused" in result["error"]  # type: ignore[reportOperatorIssue]

    @patch("core.watchdog.mikrotik_api")
    def test_online_updates_status(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute.return_value = [{"version": "7.12"}]
        check_router_health("router1")
        status = get_router_status("router1")
        assert "last_ok" in status
        assert status["alert_sent"] is False

    @patch("core.watchdog.mikrotik_api")
    def test_offline_updates_status(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute.side_effect = ConnectionError("timeout")
        check_router_health("router1")
        status = get_router_status("router1")
        assert "last_fail" in status


class TestGetRouterStatus:
    def test_returns_empty_dict_for_unknown(self):
        status = get_router_status("unknown_router")
        assert status == {}

    def test_returns_status_for_known(self):
        _router_status["router1"] = {"last_ok": datetime.now()}  # type: ignore[reportArgumentType]
        status = get_router_status("router1")
        assert "last_ok" in status


class TestGetRouterStatusDetail:
    def test_unknown_router_is_offline_with_empty_detail(self):
        detail = get_router_status_detail("unknown_router")
        assert detail["online"] is False
        assert detail["version"] is None
        assert detail["active_users"] is None

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_online_enriches_version_and_users(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        _router_status["router1"] = {"last_ok": datetime.now()}  # type: ignore[reportArgumentType]
        mock_api.get_version.return_value = "7.15.3"
        mock_stats.get_hotspot_stats.return_value = {
            "active_users": 12,
            "total_users": 30,
            "inactive_users": 18,
            "total_bytes": 0,
        }
        detail = get_router_status_detail("router1")
        assert detail["online"] is True
        assert detail["version"] == "7.15.3"
        assert detail["active_users"] == 12

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_offline_skips_live_queries(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = False
        mock_api.get_cached_version.return_value = None
        _router_status["router1"] = {"last_fail": datetime.now()}  # type: ignore[reportArgumentType]
        detail = get_router_status_detail("router1")
        assert detail["online"] is False
        assert detail["version"] is None
        assert detail["active_users"] is None
        mock_api.get_version.assert_not_called()
        mock_stats.get_hotspot_stats.assert_not_called()

    @patch("core.watchdog.stats_manager")
    @patch("core.watchdog.mikrotik_api")
    def test_version_unknown_normalized_to_none(self, mock_api, mock_stats):  # type: ignore[reportMissingParameterType]
        mock_api.has_active_connection.return_value = False
        _router_status["router1"] = {"last_ok": datetime.now()}  # type: ignore[reportArgumentType]
        mock_api.get_cached_version.return_value = "unknown"
        mock_stats.get_hotspot_stats.return_value = None
        detail = get_router_status_detail("router1")
        assert detail["version"] is None
        assert detail["active_users"] is None


class TestWasAlertSent:
    def test_returns_false_when_no_status(self):
        assert was_alert_sent("router1") is False

    def test_returns_false_when_not_sent(self):
        _router_status["router1"] = {"alert_sent": False}
        assert was_alert_sent("router1") is False

    def test_returns_true_when_sent(self):
        _router_status["router1"] = {"alert_sent": True}
        assert was_alert_sent("router1") is True


class TestMarkAlertSent:
    def test_marks_alert_sent(self):
        _router_status["router1"] = {"alert_sent": False}
        mark_alert_sent("router1")
        assert _router_status["router1"]["alert_sent"] is True

    def test_no_error_when_router_not_in_status(self):
        # Should not raise
        mark_alert_sent("unknown_router")


class TestClearStatus:
    def test_clears_existing_status(self):
        _router_status["router1"] = {"last_ok": datetime.now()}  # type: ignore[reportArgumentType]
        clear_status("router1")
        assert "router1" not in _router_status

    def test_no_error_when_clearing_nonexistent(self):
        # Should not raise
        clear_status("unknown_router")
