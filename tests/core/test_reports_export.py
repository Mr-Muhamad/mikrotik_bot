"""Tests for core.reports_export — CSV generation for hotspot users."""

from unittest.mock import patch

from core.reports_export import generate_hotspot_users_csv

MODULE = "core.reports_export"


class TestGenerateHotspotUsersCsv:
    def setup_method(self):
        self.rk = "discovered_1"

    @patch(f"{MODULE}.mikrotik_api")
    def test_returns_csv_with_header_and_rows(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = [
            {
                "name": "user1",
                "profile": "10GB",
                "limit-bytes-total": 10000000000,
                "bytes-in": 500000000,
                "bytes-out": 200000000,
                "uptime": "1d02:00:00",
                "comment": "Ahmed/22",
                "disabled": "false",
            },
        ]
        result = generate_hotspot_users_csv(self.rk)
        assert "user1" in result
        assert "10GB" in result
        assert "Ahmed" in result

    @patch(f"{MODULE}.mikrotik_api")
    def test_returns_empty_string_on_fetch_error(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.side_effect = Exception("API failure")
        result = generate_hotspot_users_csv(self.rk)
        assert result == ""

    @patch(f"{MODULE}.mikrotik_api")
    def test_empty_user_list_returns_header_only(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = []
        result = generate_hotspot_users_csv(self.rk)
        assert "Username" in result
        lines = result.strip().split("\n")
        assert len(lines) == 1

    @patch(f"{MODULE}.mikrotik_api")
    def test_disabled_user_shows_disabled_status(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = [
            {
                "name": "user2",
                "profile": "5GB",
                "limit-bytes-total": 0,
                "bytes-in": 0,
                "bytes-out": 0,
                "uptime": "00:00:00",
                "comment": "",
                "disabled": "true",
            },
        ]
        result = generate_hotspot_users_csv(self.rk)
        assert "Disabled" in result

    @patch(f"{MODULE}.mikrotik_api")
    def test_active_user_shows_active_status(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = [
            {
                "name": "user3",
                "profile": "unlimited",
                "limit-bytes-total": 0,
                "bytes-in": 1000,
                "bytes-out": 500,
                "uptime": "00:10:00",
                "comment": "",
                "disabled": "false",
            },
        ]
        result = generate_hotspot_users_csv(self.rk)
        assert "Active" in result

    @patch(f"{MODULE}.mikrotik_api")
    def test_no_limit_shows_unlimited(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = [
            {
                "name": "user4",
                "profile": "default",
                "limit-bytes-total": 0,
                "bytes-in": 0,
                "bytes-out": 0,
                "uptime": "00:00:00",
                "comment": "",
                "disabled": "false",
            },
        ]
        result = generate_hotspot_users_csv(self.rk)
        assert "غير محدد" in result

    @patch(f"{MODULE}.mikrotik_api")
    def test_multiple_users_all_present(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.execute_long.return_value = [
            {
                "name": f"user{i}",
                "profile": "p",
                "limit-bytes-total": 0,
                "bytes-in": 0,
                "bytes-out": 0,
                "uptime": "00:00:00",
                "comment": "",
                "disabled": "false",
            }
            for i in range(5)
        ]
        result = generate_hotspot_users_csv(self.rk)
        for i in range(5):
            assert f"user{i}" in result
