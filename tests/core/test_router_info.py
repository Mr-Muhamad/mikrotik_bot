"""Tests for core.router_info — subsystem detection and caching."""

from unittest.mock import patch

from core.router_info import (
    SYSTEM_BOTH,
    SYSTEM_HOTSPOT,
    SYSTEM_UNKNOWN,
    SYSTEM_USERMAN,
    cache_get,
    cache_set,
    detect_router_system,
)

MODULE = "core.router_info"


class TestCacheGetSet:
    def setup_method(self):
        import core.router_info as mod

        mod._router_system_cache.clear()  # type: ignore[reportPrivateUsage]

    def test_set_and_get(self):
        cache_set("rk1", SYSTEM_HOTSPOT)
        assert cache_get("rk1") == SYSTEM_HOTSPOT

    def test_get_missing_returns_none(self):
        assert cache_get("nonexistent") is None

    def test_overwrite(self):
        cache_set("rk1", SYSTEM_HOTSPOT)
        cache_set("rk1", SYSTEM_USERMAN)
        assert cache_get("rk1") == SYSTEM_USERMAN


class TestDetectRouterSystem:
    def setup_method(self):
        import core.router_info as mod

        mod._router_system_cache.clear()  # type: ignore[reportPrivateUsage]

    @patch(f"{MODULE}.mikrotik_api")
    def test_none_key_returns_unknown(self, mock_api):  # type: ignore[reportMissingParameterType]
        assert detect_router_system(None) == SYSTEM_UNKNOWN

    @patch(f"{MODULE}.mikrotik_api")
    def test_empty_key_returns_unknown(self, mock_api):  # type: ignore[reportMissingParameterType]
        assert detect_router_system("") == SYSTEM_UNKNOWN

    @patch(f"{MODULE}.mikrotik_api")
    def test_returns_cached_value(self, mock_api):  # type: ignore[reportMissingParameterType]
        cache_set("rk1", SYSTEM_BOTH)
        result = detect_router_system("rk1")
        assert result == SYSTEM_BOTH
        mock_api.check_connection_health.assert_not_called()

    @patch(f"{MODULE}.mikrotik_api")
    def test_healthy_router_nothing_found(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (True, None)
        mock_api.get_userman_base_path.return_value = "/tool/user-manager"
        mock_api.execute.side_effect = Exception("no such item")
        result = detect_router_system("rk1")
        assert result == SYSTEM_UNKNOWN

    @patch(f"{MODULE}.mikrotik_api")
    def test_hotspot_only(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (True, None)
        mock_api.get_userman_base_path.return_value = "/tool/user-manager"
        mock_api.execute.side_effect = [
            [],
            Exception("no userman"),
        ]
        result = detect_router_system("rk1")
        assert result == SYSTEM_HOTSPOT

    @patch(f"{MODULE}.mikrotik_api")
    def test_userman_only(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (True, None)
        mock_api.get_userman_base_path.return_value = "/tool/user-manager"
        mock_api.execute.side_effect = [
            Exception("no hotspot"),
            [],
        ]
        result = detect_router_system("rk1")
        assert result == SYSTEM_USERMAN

    @patch(f"{MODULE}.mikrotik_api")
    def test_both_subsystems(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (True, None)
        mock_api.get_userman_base_path.return_value = "/tool/user-manager"
        mock_api.execute.side_effect = [[], []]
        result = detect_router_system("rk1")
        assert result == SYSTEM_BOTH

    @patch(f"{MODULE}.mikrotik_api")
    def test_unhealthy_router_returns_unknown(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (False, "timeout")
        result = detect_router_system("rk1")
        assert result == SYSTEM_UNKNOWN

    @patch(f"{MODULE}.mikrotik_api")
    def test_exception_returns_unknown(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.side_effect = Exception("network")
        result = detect_router_system("rk1")
        assert result == SYSTEM_UNKNOWN

    @patch(f"{MODULE}.mikrotik_api")
    def test_result_is_cached(self, mock_api):  # type: ignore[reportMissingParameterType]
        mock_api.check_connection_health.return_value = (True, None)
        mock_api.get_userman_base_path.return_value = "/tool/user-manager"
        mock_api.execute.side_effect = [[], []]
        detect_router_system("rk1")
        assert cache_get("rk1") == SYSTEM_BOTH
        detect_router_system("rk1")
        assert mock_api.execute.call_count == 2
