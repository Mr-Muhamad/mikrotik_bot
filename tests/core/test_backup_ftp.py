"""Tests for core.backup.ftp — FTP download/upload helpers."""

import ftplib
import os
from unittest.mock import mock_open, patch

import pytest

# ---------------------------------------------------------------------------
# Patch helpers applied to every test in this module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_global_flag():
    """Reset the module-level warning flag between tests."""
    with patch("core.backup.ftp._ftp_plaintext_warned", False):
        yield


@pytest.fixture(autouse=True)
def _patch_api_and_port():
    """Provide easily accessible mock placeholders for mikrotik_api and get_ftp_port."""
    with (
        patch("core.backup.ftp.mikrotik_api") as mock_api,
        patch("core.backup.ftp.get_ftp_port") as mock_get_port,
    ):
        mock_get_port.return_value = 21
        yield mock_api, mock_get_port


def _ftp_info():
    return {"host": "192.168.1.1", "user": "admin", "password": "secret", "port": 21}


# ===================================================================
# _warn_plaintext_ftp
# ===================================================================


class TestWarnPlaintextFtp:
    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp.logger")
    def test_warn_plaintext_ftp_logs_once(self, mock_logger, _mock_ftp):
        from core.backup.ftp import _warn_plaintext_ftp

        with patch("core.backup.ftp._ftp_plaintext_warned", False):
            _warn_plaintext_ftp()
            _warn_plaintext_ftp()

        assert mock_logger.warning.call_count == 1

    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp.logger")
    def test_warn_plaintext_ftp_sets_flag(self, mock_logger, _mock_ftp):
        import core.backup.ftp as mod

        with patch.object(mod, "_ftp_plaintext_warned", False):
            mod._warn_plaintext_ftp()
            assert mod._ftp_plaintext_warned is True

    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp.logger")
    def test_warn_plaintext_ftp_no_log_when_already_warned(self, mock_logger, _mock_ftp):
        from core.backup.ftp import _warn_plaintext_ftp

        with patch("core.backup.ftp._ftp_plaintext_warned", True):
            _warn_plaintext_ftp()

        mock_logger.warning.assert_not_called()

    def test_flag_exposed_in_module(self):
        import core.backup.ftp as mod

        assert hasattr(mod, "_ftp_plaintext_warned")


# ===================================================================
# get_router_ftp_info
# ===================================================================


class TestGetRouterFtpInfo:
    def test_success(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "admin",
            "password": "pw",
        }

        result = get_router_ftp_info("router1", 21)

        assert result == {"host": "10.0.0.1", "user": "admin", "password": "pw", "port": 21}
        mock_api.get_router_info.assert_called_once_with("router1")

    def test_returns_none_on_exception(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = ConnectionError("refused")

        result = get_router_ftp_info("router_bad", 21)
        assert result is None

    def test_returns_none_on_key_error(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {}

        result = get_router_ftp_info("router_missing", 21)
        assert result is None

    def test_uses_provided_port(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "u",
            "password": "p",
        }

        result = get_router_ftp_info("r1", 9999)
        assert result is not None
        assert result["port"] == 9999

    def test_returns_none_on_timeout_error(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = TimeoutError("timed out")

        assert get_router_ftp_info("r1", 21) is None


# ===================================================================
# download_files_via_ftp
# ===================================================================


class TestDownloadFilesViaFtp:
    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_single_file(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "admin",
            "password": "pw",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = lambda cmd, cb: cb(b"file-content")

        with patch("builtins.open", mock_open()) as m:
            result = download_files_via_ftp("r1", "/tmp/backup", ["backup.backup"])

        assert result == ["backup.backup"]
        ftp_inst.connect.assert_called_once_with("10.0.0.1", 21, timeout=10)
        ftp_inst.set_pasv.assert_called_once_with(True)
        ftp_inst.login.assert_called_once_with("admin", "pw")
        ftp_inst.quit.assert_called_once()
        m().write.assert_called_with(b"file-content")

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_multiple_files(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = lambda cmd, cb: cb(b"data")

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["f1.backup", "f2.backup", "f3.rsc"])

        assert result == ["f1.backup", "f2.backup", "f3.rsc"]
        assert ftp_inst.retrbinary.call_count == 3

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_skips_failed_file(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        call_count = [0]

        def fake_retrbinary(cmd, cb):
            call_count[0] += 1
            if "fail_file" in cmd:
                raise ftplib.Error("transfer error")
            cb(b"ok")

        ftp_inst.retrbinary.side_effect = fake_retrbinary

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp(
                "r1", "/tmp", ["good.backup", "fail_file.backup", "also_good.rsc"]
            )

        assert "good.backup" in result
        assert "fail_file.backup" not in result
        assert "also_good.rsc" in result

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_skips_on_timeout_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        def fake_retrbinary(cmd, cb):
            if "timeout" in cmd:
                raise TimeoutError("timed out")
            cb(b"data")

        ftp_inst.retrbinary.side_effect = fake_retrbinary

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["timeout.file", "ok.file"])

        assert result == ["ok.file"]

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_skips_on_os_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        def fake_retrbinary(cmd, cb):
            if "os_err" in cmd:
                raise OSError("disk full")
            cb(b"data")

        ftp_inst.retrbinary.side_effect = fake_retrbinary

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["os_err.file", "ok.file"])

        assert result == ["ok.file"]

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_skips_on_eof_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        def fake_retrbinary(cmd, cb):
            if "eof" in cmd:
                raise EOFError("connection reset")
            cb(b"data")

        ftp_inst.retrbinary.side_effect = fake_retrbinary

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["eof.file"])

        assert result == []

    def test_download_returns_empty_when_no_credentials(self, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = Exception("no router")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    def test_download_returns_empty_when_credentials_none(self, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = None

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_returns_empty_on_connection_timeout(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = TimeoutError("connect timeout")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_returns_empty_on_os_connection_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = OSError("network unreachable")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_returns_empty_on_ftplib_connection_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = ftplib.Error("connection refused")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_returns_empty_on_login_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "bad",
            "password": "creds",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.login.side_effect = ftplib.error_perm("login failed")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_returns_empty_list_when_files_to_get_empty(
        self, MockFTP, _patch_api_and_port
    ):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }

        result = download_files_via_ftp("r1", "/tmp", [])
        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_empty_credentials_skips_connection(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = ValueError("not found")

        result = download_files_via_ftp("r1", "/tmp", ["f.backup"])
        assert result == []
        MockFTP.return_value.connect.assert_not_called()

    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp._warn_plaintext_ftp")
    def test_download_calls_warn_plaintext(self, mock_warn, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = lambda cmd, cb: cb(b"x")

        with patch("builtins.open", mock_open()):
            download_files_via_ftp("r1", "/tmp", ["f.backup"])

        mock_warn.assert_called_once()

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_uses_correct_retr_command(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = lambda cmd, cb: cb(b"")

        with patch("builtins.open", mock_open()):
            download_files_via_ftp("r1", "/tmp", ["my_backup.backup"])

        ftp_inst.retrbinary.assert_called_once()
        cmd_arg = ftp_inst.retrbinary.call_args[0][0]
        assert cmd_arg == "RETR my_backup.backup"

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_local_path_uses_backup_dir(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = lambda cmd, cb: cb(b"d")

        with patch("builtins.open", mock_open()) as m:
            download_files_via_ftp("r1", "/data/backups", ["test.backup"])

        opened_path = m.call_args[0][0]
        assert opened_path == os.path.join("/data/backups", "test.backup")


# ===================================================================
# upload_file_via_ftp
# ===================================================================


class TestUploadFileViaFtp:
    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_success(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "admin",
            "password": "pw",
        }
        ftp_inst = MockFTP.return_value

        with patch("builtins.open", mock_open(read_data=b"payload")):
            result = upload_file_via_ftp("r1", "/tmp/file.backup", "remote.backup")

        assert result is True
        ftp_inst.connect.assert_called_once_with("10.0.0.1", 21, timeout=10)
        ftp_inst.set_pasv.assert_called_once_with(True)
        ftp_inst.login.assert_called_once_with("admin", "pw")
        ftp_inst.storbinary.assert_called_once()
        stor_cmd = ftp_inst.storbinary.call_args[0][0]
        assert stor_cmd == "STOR remote.backup"
        ftp_inst.quit.assert_called_once()

    def test_upload_returns_false_when_no_credentials(self, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = Exception("no router")

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_connection_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = OSError("no route")

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_timeout(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = TimeoutError("timed out")

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_ftplib_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.login.side_effect = ftplib.error_perm("denied")

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_eof_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = EOFError("reset")

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_storbinary_error(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.storbinary.side_effect = ftplib.Error("write failed")

        with patch("builtins.open", mock_open(read_data=b"data")):
            result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")

        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp._warn_plaintext_ftp")
    def test_upload_calls_warn_plaintext(self, mock_warn, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }

        with patch("builtins.open", mock_open(read_data=b"x")):
            upload_file_via_ftp("r1", "/tmp/f", "remote.f")

        mock_warn.assert_called_once()

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_uses_correct_stor_command(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        with patch("builtins.open", mock_open(read_data=b"content")):
            upload_file_via_ftp("r1", "/tmp/f", "destination_name.backup")

        stor_cmd = ftp_inst.storbinary.call_args[0][0]
        assert stor_cmd == "STOR destination_name.backup"

    def test_upload_returns_false_when_router_info_none(self, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = None

        result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")
        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_uses_provided_port(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, mock_get_port = _patch_api_and_port
        mock_get_port.return_value = 8728
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        with patch("builtins.open", mock_open(read_data=b"d")):
            upload_file_via_ftp("r1", "/tmp/f", "remote.f")

        ftp_inst.connect.assert_called_once_with("10.0.0.1", 8728, timeout=10)


# ===================================================================
# Edge cases / integration
# ===================================================================


class TestDownloadEdgeCases:
    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_all_files_fail_returns_empty(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = ftplib.Error("always fail")

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["a.backup", "b.backup"])

        assert result == []

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_quits_even_when_exception_occurs(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = EOFError("reset")

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["f.backup"])

        assert result == []
        ftp_inst.quit.assert_called_once()

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_connect_timeout_still_quits_for_cleanup(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.connect.side_effect = TimeoutError("timeout")

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp("r1", "/tmp", ["f.backup"])

        assert result == []
        ftp_inst.quit.assert_called_once()

    @patch("core.backup.ftp.ftplib.FTP")
    def test_download_partial_failure_logs_correctly(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import download_files_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value

        def fake_retr(cmd, cb):
            if "bad" in cmd:
                raise ftplib.Error("bad transfer")
            cb(b"data")

        ftp_inst.retrbinary.side_effect = fake_retr

        with patch("builtins.open", mock_open()):
            result = download_files_via_ftp(
                "r1", "/tmp", ["ok1.backup", "bad.backup", "ok2.backup"]
            )

        assert result == ["ok1.backup", "ok2.backup"]
        assert ftp_inst.quit.call_count == 1


class TestUploadEdgeCases:
    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_quits_even_when_storbinary_fails(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.storbinary.side_effect = ftplib.Error("upload failed")

        with patch("builtins.open", mock_open(read_data=b"d")):
            upload_file_via_ftp("r1", "/tmp/f", "remote.f")

        ftp_inst.quit.assert_called_once()

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_returns_false_on_file_not_found(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }

        with patch("builtins.open", side_effect=FileNotFoundError("no such file")):
            result = upload_file_via_ftp("r1", "/nonexistent", "remote.f")

        assert result is False

    @patch("core.backup.ftp.ftplib.FTP")
    def test_upload_os_error_during_stor_returns_false(self, MockFTP, _patch_api_and_port):
        from core.backup.ftp import upload_file_via_ftp

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "10.0.0.1",
            "user": "a",
            "password": "b",
        }
        ftp_inst = MockFTP.return_value
        ftp_inst.storbinary.side_effect = OSError("disk full")

        with patch("builtins.open", mock_open(read_data=b"data")):
            result = upload_file_via_ftp("r1", "/tmp/f", "remote.f")

        assert result is False


class TestGetRouterFtpInfoEdgeCases:
    def test_returns_none_on_runtime_error(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = RuntimeError("unexpected")

        assert get_router_ftp_info("r1", 21) is None

    def test_returns_none_on_value_error(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.side_effect = ValueError("bad value")

        assert get_router_ftp_info("r1", 21) is None

    def test_returns_full_dict_on_success(self, _patch_api_and_port):
        from core.backup.ftp import get_router_ftp_info

        mock_api, _ = _patch_api_and_port
        mock_api.get_router_info.return_value = {
            "host": "172.16.0.1",
            "user": "root",
            "password": "hunter2",
        }

        result = get_router_ftp_info("my_router", 2121)
        assert result is not None
        assert result["host"] == "172.16.0.1"
        assert result["user"] == "root"
        assert result["password"] == "hunter2"
        assert result["port"] == 2121
        assert len(result) == 4
