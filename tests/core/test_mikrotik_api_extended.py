"""Extended tests for core.mikrotik_api covering missing lines to reach 90%+ coverage."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from librouteros.exceptions import LibRouterosError

from core.mikrotik_api import MikrotikAPI


@pytest.fixture
def api():
    return MikrotikAPI()


MOCK_ROUTER_INFO = {
    "host": "1.2.3.4",
    "port": 8728,
    "user": "admin",
    "password": "pass",
    "name": "test_router",
}


def _patch_pool_for_retry(api_obj, exc_class, exc_msg):
    """Return a tuple of context-manager patches to exhaust retries for execute."""
    return (
        patch.object(api_obj._pool, "get_connection", side_effect=exc_class(exc_msg)),
        patch.object(api_obj._pool, "close_connection"),
        patch.object(api_obj._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
        patch.object(api_obj._pool, "_connect", side_effect=exc_class(exc_msg)),
        patch("core.mikrotik_api.time.sleep"),
    )


class TestGetVersionOSError:
    def test_os_error_returns_unknown(self, api):
        with ExitStack() as stack:
            stack.enter_context(patch.object(api._pool, "get_version", return_value=""))
            for cm in _patch_pool_for_retry(api, OSError, "network down"):
                stack.enter_context(cm)
            result = api.get_version("r1")
        assert result == "unknown"

    def test_connection_error_returns_unknown(self, api):
        with ExitStack() as stack:
            stack.enter_context(patch.object(api._pool, "get_version", return_value=""))
            for cm in _patch_pool_for_retry(api, ConnectionError, "reset"):
                stack.enter_context(cm)
            result = api.get_version("r1")
        assert result == "unknown"


class TestGetUsermanBasePathUnknown:
    def test_unknown_version_defaults_to_v6(self, api):
        with patch.object(api, "get_version", return_value="unknown"):
            assert api.get_userman_base_path("r1") == "tool/user-manager"

    def test_empty_version_defaults_to_v6(self, api):
        with patch.object(api, "get_version", return_value=""):
            assert api.get_userman_base_path("r1") == "tool/user-manager"

    def test_version_above_7_returns_v7_path(self, api):
        with patch.object(api, "get_version", return_value="8.0"):
            assert api.get_userman_base_path("r1") == "user-manager"


class TestGetUsermanBasePathParseError:
    def test_value_error_on_non_numeric(self, api):
        with patch.object(api, "get_version", return_value="abc.def"):
            assert api.get_userman_base_path("r1") == "tool/user-manager"

    def test_index_error_on_empty_split(self, api):
        with patch.object(api, "get_version", return_value=""):
            assert api.get_userman_base_path("r1") == "tool/user-manager"


class TestClose:
    def test_close_delegates_to_pool(self, api):
        with patch.object(api._pool, "close_all") as mock_close:
            api.close()
        mock_close.assert_called_once()


class TestGetRouterInfo:
    def test_delegates_to_pool(self, api):
        info = {"host": "1.2.3.4", "port": 8728}
        with patch.object(api._pool, "get_router_info", return_value=info):
            assert api.get_router_info("r1") == info


class TestHasActiveConnection:
    def test_returns_true(self, api):
        with patch.object(api._pool, "has_active_connection", return_value=True):
            assert api.has_active_connection("r1") is True

    def test_returns_false(self, api):
        with patch.object(api._pool, "has_active_connection", return_value=False):
            assert api.has_active_connection("r1") is False


class TestCheckConnectionHealth:
    def test_healthy(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[{"version": "7.10"}])
        with patch.object(api._pool, "get_connection", return_value=fake):
            ok, msg = api.check_connection_health("r1")
        assert ok is True
        assert msg == "healthy"

    def test_empty_response(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[])
        with patch.object(api._pool, "get_connection", return_value=fake):
            ok, msg = api.check_connection_health("r1")
        assert ok is False
        assert msg == "empty_response"

    def test_librouteros_error(self, api):
        with (
            patch.object(api._pool, "get_connection", side_effect=LibRouterosError("fail")),
            patch.object(api._pool, "close_connection"),
            patch.object(api._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
            patch.object(api._pool, "_connect", return_value=MagicMock()),
        ):
            ok, msg = api.check_connection_health("r1")
        assert ok is False
        assert "fail" in msg

    def test_connection_error(self, api):
        with (
            patch.object(api._pool, "get_connection", side_effect=ConnectionError("reset")),
            patch.object(api._pool, "close_connection"),
            patch.object(api._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
            patch.object(api._pool, "_connect", return_value=MagicMock()),
        ):
            ok, msg = api.check_connection_health("r1")
        assert ok is False

    def test_os_error(self, api):
        with (
            patch.object(api._pool, "get_connection", side_effect=OSError("network")),
            patch.object(api._pool, "close_connection"),
            patch.object(api._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
            patch.object(api._pool, "_connect", return_value=MagicMock()),
        ):
            ok, msg = api.check_connection_health("r1")
        assert ok is False


class TestThrottleSleep:
    def test_sleeps_when_needed(self, api):
        api._last_api_call["r1"] = 0.0
        with patch("core.mikrotik_api.time") as mock_time:
            mock_time.monotonic.return_value = 0.05
            mock_time.sleep = MagicMock()
            api._throttle("r1")
            mock_time.sleep.assert_called_once()

    def test_no_sleep_when_enough_time_passed(self, api):
        api._last_api_call["r1"] = 0.0
        with patch("core.mikrotik_api.time") as mock_time:
            mock_time.monotonic.return_value = 1.0
            mock_time.sleep = MagicMock()
            api._throttle("r1")
            mock_time.sleep.assert_not_called()


class TestExecuteWithRetryLastExc:
    def test_raises_last_exc_after_all_retries_oserror(self, api):
        with (
            patch.object(api._pool, "get_connection", side_effect=OSError("persistent")),
            patch.object(api._pool, "close_connection"),
            patch.object(api._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
            patch.object(api._pool, "_connect", side_effect=OSError("persistent")),
            patch("core.mikrotik_api.time.sleep"),
        ):
            with pytest.raises(OSError, match="persistent"):
                api.execute("r1", "ip/hotspot/user/print")

    def test_raises_last_exc_connection_error(self, api):
        with (
            patch.object(api._pool, "get_connection", side_effect=ConnectionError("fail")),
            patch.object(api._pool, "close_connection"),
            patch.object(api._pool, "get_router_info", return_value=MOCK_ROUTER_INFO),
            patch.object(api._pool, "_connect", side_effect=ConnectionError("fail")),
            patch("core.mikrotik_api.time.sleep"),
        ):
            with pytest.raises(ConnectionError, match="fail"):
                api.execute("r1", "system-resource/print")


class TestTestConnectionSocketFailure:
    def test_socket_oserror_returns_false(self, api):
        with patch("socket.create_connection", side_effect=OSError("Connection refused")):
            ok, msg, ident = api.test_connection("10.0.0.1", "admin", "pass", 8728)
        assert ok is False
        assert "closed/unreachable" in msg
        assert ident == ""

    def test_socket_timeout_returns_false(self, api):
        exc = OSError("timed out")
        exc.errno = 10060
        with patch("socket.create_connection", side_effect=exc):
            ok, msg, ident = api.test_connection("10.0.0.1", "admin", "pass", 8728)
        assert ok is False
        assert "closed/unreachable" in msg


class TestTestConnectionApiCloseError:
    def test_close_error_is_caught(self, api):
        mock_api = MagicMock()
        mock_api.path.return_value = MagicMock(return_value=[{"version": "7.10"}])
        mock_api.close.side_effect = RuntimeError("close failed")
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", return_value=mock_api),
        ):
            ok, msg, ident = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is True

    def test_close_error_with_identity_result(self, api):
        mock_api = MagicMock()
        mock_api.path.side_effect = [
            MagicMock(return_value=[{"version": "6.49"}]),
            MagicMock(return_value=[{"name": "Router1"}]),
        ]
        mock_api.close.side_effect = IOError("socket closed")
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", return_value=mock_api),
        ):
            ok, version, ident = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is True
        assert version == "6.49"
        assert ident == "Router1"


class TestSanitizeConnectDetail:
    def test_empty_string_returns_empty(self, api):
        assert api._sanitize_connect_detail("") == ""

    def test_password_in_detail_masked(self, api):
        raw = "Authentication failed: password=secret123"
        result = api._sanitize_connect_detail(raw)
        assert "secret123" not in result
        assert "password=***" in result

    def test_long_string_truncated(self, api):
        raw = "x" * 500
        result = api._sanitize_connect_detail(raw)
        assert len(result) == 300

    def test_token_masked(self, api):
        raw = "token: abcdef123456"
        result = api._sanitize_connect_detail(raw)
        assert "abcdef123456" not in result

    def test_secret_masked(self, api):
        raw = "secret=mysupersecret"
        result = api._sanitize_connect_detail(raw)
        assert "mysupersecret" not in result

    def test_passwd_masked(self, api):
        raw = "passwd=abc123"
        result = api._sanitize_connect_detail(raw)
        assert "abc123" not in result


class TestGetBotHostForRouter:
    def test_returns_bot_host(self, api):
        with patch("config.BOT_HOST", "192.168.1.100"):
            result = api._get_bot_host_for_router("r1")
        assert result == "192.168.1.100"

    def test_returns_empty_when_not_set(self, api):
        with patch("config.BOT_HOST", ""):
            result = api._get_bot_host_for_router("r1")
        assert result == ""


class TestUploadFileToRouter:
    def test_returns_false_when_no_bot_host(self, api):
        with patch("config.BOT_HOST", ""):
            result = api.upload_file_to_router("r1", "/tmp/file.backup", "file.backup")
        assert result is False

    def test_returns_false_on_prepare_failure(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch("core.backup.file_server.prepare_serve_file", side_effect=OSError("disk full")),
        ):
            result = api.upload_file_to_router("r1", "/tmp/file.backup", "file.backup")
        assert result is False

    def test_returns_false_on_fetch_failure(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch("core.backup.file_server.prepare_serve_file", return_value="staged_file.backup"),
            patch("core.backup.file_server.cleanup_serve_file"),
            patch.object(api, "execute_long", side_effect=OSError("timeout")),
        ):
            result = api.upload_file_to_router("r1", "/tmp/file.backup", "file.backup")
        assert result is False

    def test_success(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch("core.backup.file_server.prepare_serve_file", return_value="staged_file.backup"),
            patch("core.backup.file_server.cleanup_serve_file") as mock_cleanup,
            patch.object(api, "execute_long", return_value=[]),
        ):
            result = api.upload_file_to_router("r1", "/tmp/file.backup", "file.backup")
        assert result is True
        mock_cleanup.assert_called_once_with("staged_file.backup")

    def test_cleanup_called_even_on_failure(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch("core.backup.file_server.prepare_serve_file", return_value="staged_file.backup"),
            patch("core.backup.file_server.cleanup_serve_file") as mock_cleanup,
            patch.object(api, "execute_long", side_effect=RuntimeError("boom")),
        ):
            api.upload_file_to_router("r1", "/tmp/file.backup", "file.backup")
        mock_cleanup.assert_called_once_with("staged_file.backup")


class TestDownloadFileFromRouter:
    def test_returns_false_when_no_bot_host(self, api):
        with patch("config.BOT_HOST", ""):
            result = api.download_file_from_router("r1", "file.backup", "/tmp/backups")
        assert result is False

    def test_returns_false_on_fetch_failure(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch.object(api, "execute_long", side_effect=OSError("timeout")),
        ):
            result = api.download_file_from_router("r1", "file.backup", "/tmp/backups")
        assert result is False

    def test_success_file_found(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch.object(api, "execute_long", return_value=[]),
            patch("core.mikrotik_api.os.path.isfile", return_value=True),
            patch("core.mikrotik_api.os.makedirs"),
            patch("shutil.move"),
        ):
            result = api.download_file_from_router("r1", "file.backup", "/tmp/backups")
        assert result is True

    def test_file_not_found_in_upload_dir(self, api):
        with (
            patch("config.BOT_HOST", "10.0.0.1"),
            patch.object(api, "execute_long", return_value=[]),
            patch("core.mikrotik_api.os.path.isfile", return_value=False),
        ):
            result = api.download_file_from_router("r1", "file.backup", "/tmp/backups")
        assert result is False


class TestProbeApiSslSuccess:
    def test_ssl_probe_success_returns_hint(self, api):
        mock_probe = MagicMock()
        with patch("core.mikrotik_api.connect", return_value=mock_probe):
            result = api._probe_api_ssl("10.0.0.1", "admin", "pass")
        assert "8729" in result
        mock_probe.close.assert_called_once()

    def test_ssl_probe_close_error_still_returns_hint(self, api):
        mock_probe = MagicMock()
        mock_probe.close.side_effect = RuntimeError("close error")
        with patch("core.mikrotik_api.connect", return_value=mock_probe):
            result = api._probe_api_ssl("10.0.0.1", "admin", "pass")
        assert "8729" in result

    def test_ssl_probe_failure_returns_empty(self, api):
        with patch("core.mikrotik_api.connect", side_effect=ConnectionError("refused")):
            result = api._probe_api_ssl("10.0.0.1", "admin", "pass")
        assert result == ""


class TestClassifyConnectFailure:
    def test_timeout_winerror_10060(self, api):
        exc = OSError("Connection timed out")
        exc.winerror = 10060
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "مهلة" in msg

    def test_refused_winerror_10061(self, api):
        exc = OSError("Connection refused")
        exc.winerror = 10061
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "refused" in msg.lower()

    def test_auth_error(self, api):
        exc = LibRouterosError("invalid user or password")
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "تسجيل الدخول" in msg

    def test_generic_error(self, api):
        exc = LibRouterosError("something weird")
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "10.0.0.1" in msg

    def test_timeout_with_ssl_hint(self, api):
        exc = OSError("timed out")
        exc.errno = 10060
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728, ssl_hint="HINT")
        assert "HINT" in msg

    def test_refused_errno_10061(self, api):
        exc = OSError("Connection refused")
        exc.errno = 10061
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "refused" in msg.lower()

    def test_timeout_errno_10060(self, api):
        exc = OSError("timed out")
        exc.errno = 10060
        msg = api._classify_connect_failure(exc, "10.0.0.1", 8728)
        assert "مهلة" in msg


class TestIsTimeoutError:
    def test_winerror_10060(self, api):
        exc = OSError("fail")
        exc.winerror = 10060
        assert api._is_timeout_error(exc) is True

    def test_errno_10060(self, api):
        exc = OSError("fail")
        exc.errno = 10060
        assert api._is_timeout_error(exc) is True

    def test_timed_out_in_message(self, api):
        assert api._is_timeout_error(OSError("Connection timed out")) is True

    def test_timeout_in_message(self, api):
        assert api._is_timeout_error(OSError("Read timeout")) is True

    def test_10060_in_message(self, api):
        assert api._is_timeout_error(OSError("Error 10060")) is True

    def test_non_timeout_error(self, api):
        exc = OSError("Connection refused")
        exc.winerror = None
        exc.errno = None
        assert api._is_timeout_error(exc) is False


class TestTestConnectionTimeoutClassification:
    def test_timeout_oserror_winerror(self, api):
        exc = OSError("Connection timed out")
        exc.winerror = 10060
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=exc),
            patch.object(api, "_probe_api_ssl", return_value=""),
        ):
            ok, msg, _ = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False
        assert "مهلة" in msg or "api" in msg

    def test_refused_oserror_winerror(self, api):
        exc = OSError("Connection refused")
        exc.winerror = 10061
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=exc),
        ):
            ok, msg, _ = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False
        assert "refused" in msg.lower()

    def test_non_timeout_oserror(self, api):
        exc = OSError("Address already in use")
        exc.winerror = None
        exc.errno = None
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=exc),
            patch.object(api, "_probe_api_ssl", return_value=""),
        ):
            ok, msg, _ = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False

    def test_librouteros_login_hint(self, api):
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=LibRouterosError("invalid user: admin")),
        ):
            ok, msg, _ = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False
        assert "تسجيل الدخول" in msg


class TestCallCommand:
    def test_command_with_kwargs(self, api):
        mock_cmd_path = MagicMock(return_value=[{"name": "u1"}])
        mock_api = MagicMock()
        mock_api.path.return_value = mock_cmd_path
        result = api._call_command(mock_api, "ip/hotspot/user/add", name="u1")
        assert result == [{"name": "u1"}]
        mock_api.path.assert_called_once_with("ip", "hotspot", "user")
        mock_cmd_path.assert_called_once_with("add", name="u1")

    def test_command_without_kwargs(self, api):
        mock_cmd_path = MagicMock(return_value=[{"version": "7.10"}])
        mock_api = MagicMock()
        mock_api.path.return_value = mock_cmd_path
        result = api._call_command(mock_api, "system/resource/print")
        assert result == [{"version": "7.10"}]
        mock_cmd_path.assert_called_once_with("print")


class TestDebugLog:
    def test_masks_password_in_kwargs(self, api):
        logger = MagicMock()
        with patch("core.mikrotik_api.logger", logger):
            api._debug_log("execute", "user/add", {"name": "u1", "password": "secret"})
        logger.debug.assert_called_once()
        logged = logger.debug.call_args[0][0]
        assert "secret" not in logged
        assert "'password': '***'" in logged

    def test_empty_kwargs(self, api):
        logger = MagicMock()
        with patch("core.mikrotik_api.logger", logger):
            api._debug_log("execute", "print", {})
        logger.debug.assert_not_called()


class TestGetCachedVersion:
    def test_returns_none_for_empty(self, api):
        with patch.object(api._pool, "get_version", return_value=""):
            assert api.get_cached_version("r1") == ""

    def test_returns_cached(self, api):
        with patch.object(api._pool, "get_version", return_value="7.10"):
            assert api.get_cached_version("r1") == "7.10"


class TestConnectionContextBrokenFlag:
    def test_non_retryable_does_not_mark_broken(self, api):
        fake = MagicMock()
        fake.path.side_effect = LibRouterosError("unknown parameter")
        with (
            patch.object(api._pool, "get_connection", return_value=fake),
            patch.object(api._pool, "release_connection") as mock_release,
        ):
            with pytest.raises(LibRouterosError):
                api.execute("r1", "ip/hotspot/user/print")
        mock_release.assert_called_once()
        call_kwargs = mock_release.call_args[1]
        assert call_kwargs.get("broken") is False

    def test_generic_exception_marks_broken(self, api):
        fake = MagicMock()
        fake.path.side_effect = ValueError("weird")
        with (
            patch.object(api._pool, "get_connection", return_value=fake),
            patch.object(api._pool, "release_connection") as mock_release,
        ):
            with pytest.raises(ValueError):
                api.execute("r1", "ip/hotspot/user/print")
        mock_release.assert_called_once()
        call_kwargs = mock_release.call_args[1]
        assert call_kwargs.get("broken") is True


class TestForceReconnect:
    def test_retry_uses_reconnect(self, api):
        fail_api = MagicMock()
        fail_api.path.side_effect = OSError("connection lost")
        ok_api = MagicMock()
        ok_api.path.return_value = MagicMock(return_value=[])
        call_count = [0]

        def get_conn_side_effect(key, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return fail_api
            return ok_api

        with (
            patch.object(api._pool, "get_connection", side_effect=get_conn_side_effect),
            patch.object(api._pool, "reconnect", return_value=ok_api) as mock_reconnect,
            patch.object(api._pool, "release_connection"),
            patch("core.mikrotik_api.time.sleep"),
        ):
            result = api.execute("r1", "print")
        assert result == []
        mock_reconnect.assert_called_once()

    def test_first_attempt_uses_get_connection(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[])
        with (
            patch.object(api._pool, "get_connection", return_value=fake) as mock_get,
            patch.object(api._pool, "release_connection"),
        ):
            api._execute_with_retry("r1", "print", 30)
        mock_get.assert_called_once()


class TestExecuteLongDelegation:
    def test_execute_long_uses_long_timeout(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[])
        with (
            patch.object(api._pool, "get_connection", return_value=fake),
            patch.object(api._pool, "release_connection"),
        ):
            with patch.object(api, "_execute_with_retry", wraps=api._execute_with_retry) as mock_exec:
                api.execute_long("r1", "system/resource/print")
                assert mock_exec.call_args[0][2] == 120

    def test_execute_uses_api_timeout(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[])
        with (
            patch.object(api._pool, "get_connection", return_value=fake),
            patch.object(api._pool, "release_connection"),
        ):
            with patch.object(api, "_execute_with_retry", wraps=api._execute_with_retry) as mock_exec:
                api.execute("r1", "system/resource/print")
                assert mock_exec.call_args[0][2] == 30


class TestVersion7Detection:
    def test_version_7(self, api):
        with patch.object(api, "get_version", return_value="7.0"):
            assert api.is_version_7() is True

    def test_version_6(self, api):
        with patch.object(api, "get_version", return_value="6.49.6"):
            assert api.is_version_7() is False

    def test_unknown(self, api):
        with patch.object(api, "get_version", return_value="unknown"):
            assert api.is_version_7() is False


class TestUploadFullFlow:
    def test_url_construction(self, api):
        with (
            patch("config.BOT_HOST", "192.168.88.1"),
            patch("core.backup.file_server.prepare_serve_file", return_value="serve.backup"),
            patch("core.backup.file_server.cleanup_serve_file") as mock_cleanup,
            patch.object(api, "execute_long") as mock_exec,
        ):
            result = api.upload_file_to_router("r1", "/tmp/f.backup", "f.backup")
        assert result is True
        call_args = mock_exec.call_args
        assert call_args[0][0] == "r1"
        assert call_args[0][1] == "tool/fetch"
        assert "192.168.88.1" in str(call_args)
        mock_cleanup.assert_called_once_with("serve.backup")


class TestDownloadFullFlow:
    def test_executes_tool_fetch(self, api):
        with (
            patch("config.BOT_HOST", "192.168.88.1"),
            patch.object(api, "execute_long") as mock_exec,
            patch("core.mikrotik_api.os.path.isfile", return_value=False),
        ):
            api.download_file_from_router("r1", "backup.backup", "/tmp/backups")
        assert mock_exec.call_args[0][1] == "tool/fetch"
        kwargs = mock_exec.call_args[1]
        assert kwargs["upload"] == "yes"


class TestProbeSslFullFlow:
    def test_probe_connect_success_close_error(self, api):
        mock_probe = MagicMock()
        mock_probe.close.side_effect = IOError("already closed")
        with patch("core.mikrotik_api.connect", return_value=mock_probe) as mock_connect:
            result = api._probe_api_ssl("10.0.0.1", "admin", "pass")
        mock_connect.assert_called_once_with(
            username="admin",
            password="pass",
            host="10.0.0.1",
            port=8729,
            encoding="utf-8",
            timeout=3,
        )
        assert "8729" in result

    def test_probe_connect_raises(self, api):
        with patch("core.mikrotik_api.connect", side_effect=OSError("no route")):
            result = api._probe_api_ssl("10.0.0.1", "admin", "pass")
        assert result == ""


class TestTestConnectionFullFlow:
    def test_full_success_with_identity(self, api):
        mock_api = MagicMock()
        mock_api.path.side_effect = [
            MagicMock(return_value=[{"version": "7.12"}]),
            MagicMock(return_value=[{"name": "MikroTik-Router"}]),
        ]
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", return_value=mock_api),
        ):
            ok, version, identity = api.test_connection("192.168.1.1", "admin", "pass123")
        assert ok is True
        assert version == "7.12"
        assert identity == "MikroTik-Router"

    def test_empty_resource_and_identity(self, api):
        mock_api = MagicMock()
        mock_api.path.side_effect = [
            MagicMock(return_value=[]),
            MagicMock(return_value=[]),
        ]
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", return_value=mock_api),
        ):
            ok, version, identity = api.test_connection("192.168.1.1", "admin", "pass")
        assert ok is True
        assert version == "unknown"
        assert identity == "192.168.1.1"

    def test_os_error_non_timeout_with_ssl_probe(self, api):
        exc = OSError("Connection reset")
        exc.winerror = None
        exc.errno = None
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=exc),
            patch.object(api, "_probe_api_ssl", return_value="SSL_HINT"),
        ):
            ok, msg, identity = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False
        assert "SSL_HINT" in msg

    def test_unexpected_exception(self, api):
        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch("core.mikrotik_api.connect", side_effect=RuntimeError("unexpected")),
        ):
            ok, msg, identity = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False

    def test_no_api_obj_in_finally(self, api):
        with patch("socket.create_connection", side_effect=OSError("refused")):
            ok, msg, identity = api.test_connection("10.0.0.1", "admin", "pass")
        assert ok is False


class TestRebootSwallow:
    def test_reboot_on_os_error(self, api):
        fake = MagicMock()
        fake.path.side_effect = OSError("network")
        with (
            patch.object(api._pool, "get_connection", return_value=fake),
            patch.object(api._pool, "release_connection"),
        ):
            result = api.execute("r1", "system/reboot")
        assert result == []


class TestNonBlockingSuccess:
    def test_non_blocking_successful(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[{"done": True}])
        with patch.object(api._pool, "get_connection", return_value=fake):
            api.execute_non_blocking("r1", "tool/fetch", url="http://x")


class TestDebugLogMasking:
    def test_masks_all_password_keys(self, api):
        logger = MagicMock()
        with patch("core.mikrotik_api.logger", logger):
            api._debug_log("method", "cmd", {"user_password": "x", "secret_key": "y"})
        logged = logger.debug.call_args[0][0]
        assert "***" in logged


class TestGetVersionEmptyResult:
    def test_no_version_key_in_result(self, api):
        fake = MagicMock()
        fake.path.return_value = MagicMock(return_value=[{"identity": "Router"}])
        with (
            patch.object(api._pool, "get_version", return_value=""),
            patch.object(api._pool, "get_connection", return_value=fake),
        ):
            v = api.get_version("r1")
        assert v == "unknown"
