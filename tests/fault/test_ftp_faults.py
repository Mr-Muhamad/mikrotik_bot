"""Fault-injection tests for FTP backup helpers.

Focuses on partial-file cleanup after a failed transfer and on sanitizing
sensitive router credentials before they reach the logs.
"""

import ftplib
import os
import tempfile
from unittest.mock import mock_open, patch


def _ftp_info():
    return {"host": "192.168.1.1", "user": "admin", "password": "secret", "port": 21}


class TestRemovePartialFile:
    def test_removes_existing_file(self):
        from core.backup.ftp import _remove_partial_file  # type: ignore[reportPrivateUsage]

        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            _remove_partial_file(path)
            assert not os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_noop_when_file_missing(self):
        from core.backup.ftp import _remove_partial_file  # type: ignore[reportPrivateUsage]

        _remove_partial_file(os.path.join(tempfile.gettempdir(), "does-not-exist.backup"))

    def test_swallows_os_error(self):
        from core.backup.ftp import _remove_partial_file  # type: ignore[reportPrivateUsage]

        with (
            patch("core.backup.ftp.os.path.exists", return_value=True),
            patch("core.backup.ftp.os.remove", side_effect=OSError("permission denied")),
            patch("core.backup.ftp.logger.debug") as mock_debug,
        ):
            _remove_partial_file("/tmp/locked.backup")
        mock_debug.assert_called()

    def test_does_not_remove_when_path_missing(self):
        from core.backup.ftp import _remove_partial_file  # type: ignore[reportPrivateUsage]

        with (
            patch("core.backup.ftp.os.path.exists", return_value=False),
            patch("core.backup.ftp.os.remove") as mock_remove,
        ):
            _remove_partial_file("/tmp/absent.backup")
        mock_remove.assert_not_called()


class TestDownloadPartialCleanup:
    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp.mikrotik_api")
    def test_failed_file_removes_partial(self, mock_api, MockFTP):  # type: ignore[reportMissingParameterType]
        from core.backup.ftp import download_files_via_ftp

        mock_api.get_router_info.return_value = _ftp_info()
        ftp_inst = MockFTP.return_value

        def fake_retrbinary(cmd, cb):  # type: ignore[reportMissingParameterType]
            if "bad" in cmd:
                raise ftplib.Error("transfer aborted")
            cb(b"data")

        ftp_inst.retrbinary.side_effect = fake_retrbinary

        with (
            patch("builtins.open", mock_open()),
            patch("core.backup.ftp._remove_partial_file") as mock_remove,
        ):
            result = download_files_via_ftp("r1", "/tmp", ["good.backup", "bad.backup"])

        assert result == ["good.backup"]
        mock_remove.assert_called_once_with(os.path.join("/tmp", "bad.backup"))

    @patch("core.backup.ftp.ftplib.FTP")
    @patch("core.backup.ftp.mikrotik_api")
    def test_all_failed_files_removed(self, mock_api, MockFTP):  # type: ignore[reportMissingParameterType]
        from core.backup.ftp import download_files_via_ftp

        mock_api.get_router_info.return_value = _ftp_info()
        ftp_inst = MockFTP.return_value
        ftp_inst.retrbinary.side_effect = ftplib.Error("always fail")

        with (
            patch("builtins.open", mock_open()),
            patch("core.backup.ftp._remove_partial_file") as mock_remove,
        ):
            result = download_files_via_ftp("r1", "/tmp", ["a.backup", "b.backup"])

        assert result == []
        assert mock_remove.call_count == 2


class TestSanitizedErrors:
    @patch("core.backup.ftp.logger")
    @patch("core.backup.ftp.mikrotik_api")
    def test_credentials_masked_in_warning(self, mock_api, mock_logger):  # type: ignore[reportMissingParameterType]
        from core.backup.ftp import get_router_ftp_info

        mock_api.get_router_info.side_effect = ConnectionError(
            "login failed for password=super-secret-value"
        )

        assert get_router_ftp_info("r1", 21) is None

        mock_logger.warning.assert_called()
        rendered = " ".join(str(a) for a in mock_logger.warning.call_args.args)
        assert "super-secret-value" not in rendered

    @patch("core.backup.ftp.logger")
    @patch("core.backup.ftp.mikrotik_api")
    def test_unexpected_error_masked_in_warning(self, mock_api, mock_logger):  # type: ignore[reportMissingParameterType]
        from core.backup.ftp import get_router_ftp_info

        mock_api.get_router_info.side_effect = RuntimeError(
            "bad credential token=very-secret-token-value"
        )

        assert get_router_ftp_info("r1", 21) is None

        mock_logger.warning.assert_called()
        rendered = " ".join(str(a) for a in mock_logger.warning.call_args.args)
        assert "very-secret-token-value" not in rendered
