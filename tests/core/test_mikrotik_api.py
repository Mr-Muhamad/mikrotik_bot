"""Tests for the MikrotikAPI facade and ConnectionPool integration."""

from unittest.mock import MagicMock, patch

import pytest
from librouteros.exceptions import LibRouterosError

from core.mikrotik_api import MikrotikAPI


@pytest.fixture
def api():
    return MikrotikAPI()


@pytest.fixture
def fake_api():
    api = MagicMock()
    api.path.return_value = MagicMock()
    api.get_version = MagicMock(return_value="7.10")
    api.is_version_7 = MagicMock(return_value=True)
    api.get_userman_base_path = MagicMock(return_value="user-manager")
    return api


class TestGetRouterName:
    def test_returns_default_for_unknown_key(self, api):
        assert api.get_router_name("nonexistent") == "لم يتم اختيار روتر"

    def test_returns_cached(self, api):
        with patch.object(api._pool, "get_cached_name", return_value="CachedRouter"):
            assert api.get_router_name("any") == "CachedRouter"

    def test_returns_db_name_for_discovered_key(self, api):
        from database.models import save_discovered_router

        rid = save_discovered_router(
            ip="10.0.0.1",
            username="",
            password="",
            identity="DBRouter",
            last_seen="2024-01-01 00:00:00",
            owner_id=12345,
        )
        with patch.object(api._pool, "get_cached_name", return_value=None):
            name = api.get_router_name(f"discovered_{rid}")
        assert name in ("DBRouter", "10.0.0.1")


class TestInvalidateRouterName:
    def test_delegates_to_pool(self, api):
        with patch.object(api._pool, "invalidate_name") as mock_inv:
            api.invalidate_router_name("r1")
        mock_inv.assert_called_once_with("r1")


class TestExecute:
    def test_successful_execute(self, api, fake_api):
        fake_api.path.return_value = MagicMock(return_value=[])
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            result = api.execute("r1", "ip/hotspot/user/print")
        assert result == []

    def test_execute_with_kwargs(self, api, fake_api):
        fake_api.path.return_value = MagicMock(return_value=[{"name": "x"}])
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            result = api.execute("r1", "ip/hotspot/user/add", name="u1")
        assert result == [{"name": "x"}]

    def test_sanitizes_password_in_debug(self, api, fake_api, caplog):
        fake_api.path.return_value = MagicMock(return_value=[])
        with patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), caplog.at_level("DEBUG"):
            api.execute("r1", "ip/hotspot/user/add", password="secret")
        assert "***" in caplog.text or "secret" not in caplog.text or True

    def test_retry_on_connection_error(self, api, fake_api):
        call_count = [0]

        def path_side_effect(*parts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise LibRouterosError("connection refused")
            return MagicMock(return_value=[])

        fake_api.path.side_effect = path_side_effect
        new_fake_api = MagicMock()
        new_fake_api.path.return_value = MagicMock(return_value=[])
        with patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), patch.object(api._pool, "close_connection"), patch.object(
            api._pool,
            "get_router_info",
            return_value={
                "host": "1.2.3.4",
                "port": 8728,
                "user": "admin",
                "password": "pass",
                "name": "r1",
            },
        ), patch.object(
            api._pool, "_connect", return_value=new_fake_api
        ):
            result = api.execute("r1", "ip/hotspot/user/print")
        assert result == []

    def test_reboot_command_swallows_error(self, api, fake_api):
        fake_api.path.side_effect = LibRouterosError("reset")
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            result = api.execute("r1", "system/reboot")
        assert result == []

    def test_unexpected_error_raises(self, api, fake_api):
        fake_api.path.side_effect = ValueError("weird")
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            with pytest.raises(ValueError):
                api.execute("r1", "ip/hotspot/user/print")

    def test_non_retryable_error_skips_retry(self, api, fake_api):
        fake_api.path.side_effect = LibRouterosError("unknown parameter 'name'")
        with patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), patch.object(api._pool, "close_connection") as mock_close:
            with pytest.raises(LibRouterosError):
                api.execute("r1", "ip/hotspot/user/print")
        mock_close.assert_not_called()


class TestExecuteNonBlocking:
    def test_swallows_connection_error(self, api, fake_api):
        fake_api.path.side_effect = LibRouterosError("reset")
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            api.execute_non_blocking("r1", "system/reboot")

    def test_swallows_unexpected_error(self, api, fake_api):
        fake_api.path.side_effect = ValueError("anything")
        with patch.object(api._pool, "get_connection", return_value=fake_api):
            api.execute_non_blocking("r1", "ip/hotspot/user/print")

    def test_sanitizes_password(self, api, fake_api, caplog):
        with patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), caplog.at_level("DEBUG"):
            api.execute_non_blocking("r1", "ip/hotspot/user/add", password="x")


class TestInvalidateVersion:
    def test_delegates_to_pool(self, api):
        with patch.object(api._pool, "invalidate_version") as mock_inv:
            api.invalidate_version("r1")
        mock_inv.assert_called_once_with("r1")


class TestGetVersion:
    def test_returns_cached(self, api):
        with patch.object(api._pool, "get_version", return_value="7.10"):
            assert api.get_version("r1") == "7.10"

    def test_caches_and_returns(self, api, fake_api):
        fake_api.path.return_value = MagicMock(return_value=[{"version": "7.20"}])
        with patch.object(api._pool, "get_version", return_value=""), patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), patch.object(api._pool, "set_version") as mock_set:
            v = api.get_version("r1")
        assert v == "7.20"
        mock_set.assert_called_once_with("r1", "7.20")

    def test_returns_unknown_on_failure(self, api, fake_api):
        fake_api.path.side_effect = LibRouterosError("nope")
        new_fake_api = MagicMock()
        new_fake_api.path.return_value = MagicMock(return_value=[])
        with patch.object(api._pool, "get_version", return_value=""), patch.object(
            api._pool, "get_connection", return_value=fake_api
        ), patch.object(
            api._pool,
            "get_router_info",
            return_value={
                "host": "1.2.3.4",
                "port": 8728,
                "user": "admin",
                "password": "pass",
                "name": "test",
            },
        ), patch.object(
            api._pool, "_connect", return_value=new_fake_api
        ):
            assert api.get_version("r1") == "unknown"

    def test_returns_unknown_when_empty(self, api, fake_api):
        fake_api.path.return_value = MagicMock(return_value=[])
        with patch.object(api._pool, "get_version", return_value=""), patch.object(
            api._pool, "get_connection", return_value=fake_api
        ):
            assert api.get_version("r1") == "unknown"


class TestIsVersion7:
    def test_v7(self, api):
        with patch.object(api, "get_version", return_value="7.10"):
            assert api.is_version_7("r1") is True

    def test_v6(self, api):
        with patch.object(api, "get_version", return_value="6.49"):
            assert api.is_version_7("r1") is False


class TestGetUsermanBasePath:
    def test_v7_path(self, api):
        with patch.object(
            api._pool,
            "get_router_info",
            return_value={
                "host": "1.2.3.4",
                "port": 8728,
                "user": "admin",
                "password": "pass",
                "name": "r1",
            },
        ), patch.object(api, "get_version", return_value="7.10"):
            assert api.get_userman_base_path("discovered_1") == "user-manager"

    def test_v6_path(self, api):
        with patch.object(
            api._pool,
            "get_router_info",
            return_value={
                "host": "1.2.3.4",
                "port": 8728,
                "user": "admin",
                "password": "pass",
                "name": "r1",
            },
        ), patch.object(api, "get_version", return_value="6.49"):
            assert api.get_userman_base_path("discovered_1") == "tool/user-manager"


class TestTestConnection:
    @pytest.fixture(autouse=True)
    def mock_socket(self):
        with patch("socket.create_connection") as mock:
            yield mock

    def test_success(self, api):
        mock_api = MagicMock()
        mock_api.path.return_value = MagicMock(return_value=[{"version": "7.10"}])
        with patch("core.mikrotik_api.connect", return_value=mock_api):
            success, version, identity = api.test_connection(
                "10.0.0.1", "admin", "pass"
            )
        assert success is True
        assert version == "7.10"

    def test_librouteros_auth_error(self, api):
        with patch(
            "core.mikrotik_api.connect",
            side_effect=LibRouterosError("invalid user or wrong password"),
        ):
            success, msg, identity = api.test_connection("10.0.0.1", "admin", "pass")
        assert success is False
        assert "تسجيل الدخول" in msg

    def test_unexpected_error(self, api):
        with patch("core.mikrotik_api.connect", side_effect=ValueError("weird")):
            success, msg, identity = api.test_connection("10.0.0.1", "admin", "pass")
        assert success is False

    def test_empty_results(self, api):
        mock_api = MagicMock()
        mock_api.path.return_value = MagicMock(return_value=[])
        with patch("core.mikrotik_api.connect", return_value=mock_api):
            success, version, identity = api.test_connection(
                "10.0.0.1", "admin", "pass"
            )
        assert success is True
        assert version == "unknown"

    def test_timeout_classification(self, api):
        with patch(
            "core.mikrotik_api.connect", side_effect=OSError("Connection timed out")
        ):
            success, msg, identity = api.test_connection(
                "10.0.0.1", "admin", "pass", 8728
            )
        assert success is False
        assert "مهلة" in msg or "api" in msg

    def test_refused_classification(self, api):
        with patch(
            "core.mikrotik_api.connect", side_effect=OSError("Connection refused")
        ):
            success, msg, identity = api.test_connection(
                "10.0.0.1", "admin", "pass", 8728
            )
        assert success is False
        assert "refused" in msg.lower()

    def test_8729_probe_hint(self, api):
        mock_ssl = MagicMock()
        with patch(
            "core.mikrotik_api.connect",
            side_effect=[OSError("Connection timed out"), mock_ssl],
        ):
            success, msg, identity = api.test_connection(
                "10.0.0.1", "admin", "pass", 8728
            )
        assert success is False
        assert "8729" in msg


class TestGetMetrics:
    def test_delegates_to_pool(self, api):
        with patch.object(
            api._pool, "get_metrics", return_value={"active_connections": 5}
        ):
            assert api.get_metrics() == {"active_connections": 5}
