"""Extended tests for core/backup/file_server.py — cover successful upload,
successful download, start/stop server, log_message, and cleanup error paths."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from core.backup.file_server import (
    _FileRequestHandler,  # type: ignore[reportPrivateUsage]
    cleanup_serve_file,
    prepare_serve_file,
    start_file_server,
    stop_file_server,
)


def _make_handler(method, path, headers, body=b""):  # type: ignore[reportMissingParameterType]
    handler = MagicMock(spec=_FileRequestHandler)
    handler.path = path
    handler.headers = headers
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.send_error = MagicMock()
    handler.send_error.side_effect = lambda c, m="": None
    return handler


class TestDoPostSuccess:
    def test_successful_upload(self, tmp_path):  # type: ignore[reportMissingParameterType]
        handler = _make_handler(
            "POST",
            "/upload",
            {
                "Authorization": "Bearer test-secret",
                "Content-Length": "4",
                "X-Filename": "test.backup",
                "X-Router-Key": "router1",
            },
            b"data",
        )
        with (
            patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"),
            patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)),
        ):
            _FileRequestHandler.do_POST(handler)
        handler.send_response.assert_called_with(200)
        upload_file = tmp_path / "uploads" / "router1" / "test.backup"
        assert upload_file.exists()
        assert upload_file.read_bytes() == b"data"

    def test_upload_missing_content_length_defaults_zero(self, tmp_path):  # type: ignore[reportMissingParameterType]
        handler = _make_handler(
            "POST",
            "/upload",
            {
                "Authorization": "Bearer test-secret",
                "X-Filename": "test.backup",
                "X-Router-Key": "r1",
            },
            b"",
        )
        with (
            patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"),
            patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)),
        ):
            _FileRequestHandler.do_POST(handler)
        handler.send_response.assert_called_with(200)

    def test_upload_missing_x_filename_header(self):
        handler = _make_handler(
            "POST",
            "/upload",
            {
                "Authorization": "Bearer test-secret",
                "Content-Length": "4",
            },
            b"data",
        )
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(handler)
        handler.send_error.assert_called()


class TestDoGetSuccess:
    def test_successful_download(self, tmp_path):  # type: ignore[reportMissingParameterType]
        serves_dir = tmp_path / "serves"
        serves_dir.mkdir()
        f = serves_dir / "test.backup"
        f.write_bytes(b"file contents here")

        handler = _make_handler(
            "GET",
            "/files/test.backup",
            {"Authorization": "Bearer test-secret"},
        )
        with (
            patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"),
            patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)),
        ):
            _FileRequestHandler.do_GET(handler)
        handler.send_response.assert_called_with(200)
        handler.send_header.assert_any_call("Content-Length", "18")

    def test_get_empty_filename(self):
        handler = _make_handler(
            "GET",
            "/files/",
            {"Authorization": "Bearer test-secret"},
        )
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_GET(handler)
        handler.send_error.assert_called()

    def test_get_backslash_in_filename(self):
        handler = _make_handler(
            "GET",
            "/files/..\\secret",
            {"Authorization": "Bearer test-secret"},
        )
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_GET(handler)
        handler.send_error.assert_called()


class TestStartStopServer:
    def test_start_creates_server(self):
        import core.backup.file_server as fs

        fs._server = None  # type: ignore[reportPrivateUsage]
        fs._server_thread = None  # type: ignore[reportPrivateUsage]
        with patch.object(fs, "_ThreadingHTTPServer") as mock_cls:
            mock_server = MagicMock()
            mock_cls.return_value = mock_server
            start_file_server()
            mock_cls.assert_called_once()
            fs._server = None  # type: ignore[reportPrivateUsage]
            fs._server_thread = None  # type: ignore[reportPrivateUsage]

    def test_start_already_running(self):
        import core.backup.file_server as fs

        fs._server = MagicMock()  # type: ignore[reportPrivateUsage]
        fs._server_thread = MagicMock()  # type: ignore[reportPrivateUsage]
        start_file_server()
        fs._server = None  # type: ignore[reportPrivateUsage]
        fs._server_thread = None  # type: ignore[reportPrivateUsage]

    def test_stop_shuts_down(self):
        import core.backup.file_server as fs

        mock_server = MagicMock()
        fs._server = mock_server  # type: ignore[reportPrivateUsage]
        fs._server_thread = MagicMock()  # type: ignore[reportPrivateUsage]
        stop_file_server()
        mock_server.shutdown.assert_called_once()
        assert fs._server is None  # type: ignore[reportPrivateUsage]
        assert fs._server_thread is None  # type: ignore[reportPrivateUsage]

    def test_stop_when_no_server(self):
        import core.backup.file_server as fs

        fs._server = None  # type: ignore[reportPrivateUsage]
        fs._server_thread = None  # type: ignore[reportPrivateUsage]
        stop_file_server()


class TestLogMessage:
    def test_log_message_calls_logger(self):
        handler = MagicMock(spec=_FileRequestHandler)
        with patch("core.backup.file_server.logger") as mock_logger:
            _FileRequestHandler.log_message(handler, "test %s", "msg")
            mock_logger.debug.assert_called()


class TestCleanupServeFileExtended:
    def test_cleanup_oserror_handled(self, tmp_path):  # type: ignore[reportMissingParameterType]
        serves_dir = tmp_path / "serves"
        serves_dir.mkdir()
        f = serves_dir / "test.backup"
        f.write_bytes(b"data")
        with (
            patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)),
            patch("os.remove", side_effect=OSError("permission denied")),
        ):
            cleanup_serve_file("test.backup")

    def test_prepare_creates_serves_dir(self, tmp_path):  # type: ignore[reportMissingParameterType]
        src = tmp_path / "source.backup"
        src.write_bytes(b"content")
        serve_dir = tmp_path / "serves"
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            result = prepare_serve_file(str(src), "out.backup")
        assert result == "out.backup"
        assert (serve_dir / "out.backup").exists()

    def test_prepare_backslash_traversal(self, tmp_path):  # type: ignore[reportMissingParameterType]
        src = tmp_path / "x.backup"
        src.write_bytes(b"d")
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            with pytest.raises(ValueError, match="path traversal"):
                prepare_serve_file(str(src), "..\\escape.backup")
