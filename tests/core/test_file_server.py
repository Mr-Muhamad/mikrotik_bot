"""Tests for core.backup.file_server — HTTP file-transfer server."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from core.backup.file_server import (
    _MAX_UPLOAD_BYTES,
    _FileRequestHandler,
    cleanup_serve_file,
    prepare_serve_file,
)


def _make_handler(method: str, path: str, headers: dict, body: bytes = b""):
    handler = MagicMock(spec=_FileRequestHandler)
    handler.path = path
    handler.headers = headers
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.send_error = MagicMock()
    handler.wfile = BytesIO()

    def _send_error(code, msg=""):
        handler.send_error(code, msg)

    handler.send_error.side_effect = _send_error
    return handler


def _auth_header() -> dict:
    return {"Authorization": "Bearer test-secret"}


class TestCheckAuth:
    def setup_method(self):
        self.handler = MagicMock(spec=_FileRequestHandler)
        self.handler.send_error = MagicMock()
        self.handler.headers = {}

    def test_valid_token_passes(self):
        self.handler.headers = {"Authorization": "Bearer test-secret"}
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            result = _FileRequestHandler._check_auth(self.handler)
        assert result is True

    def test_invalid_token_fails(self):
        self.handler.headers = {"Authorization": "Bearer wrong"}
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            result = _FileRequestHandler._check_auth(self.handler)
        assert result is False
        self.handler.send_error.assert_called_once()

    def test_missing_header_fails(self):
        self.handler.headers = {}
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            result = _FileRequestHandler._check_auth(self.handler)
        assert result is False

    def test_empty_auth_fails(self):
        self.handler.headers = {"Authorization": ""}
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            result = _FileRequestHandler._check_auth(self.handler)
        assert result is False


class TestDoPost:
    def setup_method(self):
        self.handler = MagicMock(spec=_FileRequestHandler)
        self.handler.path = "/upload"
        self.handler.headers = {
            "Authorization": "Bearer test-secret",
            "Content-Length": "4",
            "X-Filename": "test.backup",
            "X-Router-Key": "router1",
        }
        self.handler.rfile = BytesIO(b"data")
        self.handler.wfile = BytesIO()
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.send_error = MagicMock()
        self.handler.send_error.side_effect = lambda c, m="": None

    def test_rejects_wrong_path(self):
        self.handler.path = "/wrong"
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(self.handler)
        self.handler.send_error.assert_called()

    def test_rejects_oversized_file(self):
        self.handler.headers["Content-Length"] = str(_MAX_UPLOAD_BYTES + 1)
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(self.handler)
        self.handler.send_error.assert_called()

    def test_rejects_disallowed_extension(self):
        self.handler.headers["X-Filename"] = "malware.exe"
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(self.handler)
        self.handler.send_error.assert_called()

    def test_rejects_path_traversal_in_filename(self):
        self.handler.headers["X-Filename"] = "../../etc/passwd"
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(self.handler)
        self.handler.send_error.assert_called()

    def test_rejects_empty_filename(self):
        self.handler.headers["X-Filename"] = ""
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_POST(self.handler)
        self.handler.send_error.assert_called()


class TestDoGet:
    def setup_method(self):
        self.handler = MagicMock(spec=_FileRequestHandler)
        self.handler.headers = {"Authorization": "Bearer test-secret"}
        self.handler.wfile = BytesIO()
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.send_error = MagicMock()
        self.handler.send_error.side_effect = lambda c, m="": None

    def test_rejects_non_files_path(self):
        self.handler.path = "/other"
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_GET(self.handler)
        self.handler.send_error.assert_called()

    def test_rejects_traversal_in_filename(self):
        self.handler.path = "/files/../../secret"
        with patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"):
            _FileRequestHandler.do_GET(self.handler)
        self.handler.send_error.assert_called()

    def test_returns_404_for_missing_file(self):
        self.handler.path = "/files/nonexistent.backup"
        with (
            patch("core.backup.file_server.FILE_SERVER_SECRET", "test-secret"),
            patch("core.backup.file_server.BACKUP_DIR", "/tmp/nonexistent"),
        ):
            _FileRequestHandler.do_GET(self.handler)
        self.handler.send_error.assert_called()


class TestMaxUploadBytes:
    def test_constant_is_100mb(self):
        assert _MAX_UPLOAD_BYTES == 100 * 1024 * 1024


class TestAllowedExtensions:
    def test_backup_allowed(self):
        from core.backup.file_server import _ALLOWED_EXTENSIONS

        assert ".backup" in _ALLOWED_EXTENSIONS

    def test_rsc_allowed(self):
        from core.backup.file_server import _ALLOWED_EXTENSIONS

        assert ".rsc" in _ALLOWED_EXTENSIONS

    def test_tar_allowed(self):
        from core.backup.file_server import _ALLOWED_EXTENSIONS

        assert ".tar" in _ALLOWED_EXTENSIONS

    def test_umb_allowed(self):
        from core.backup.file_server import _ALLOWED_EXTENSIONS

        assert ".umb" in _ALLOWED_EXTENSIONS


class TestPrepareAndServeFile:
    def test_prepare_copies_file(self, tmp_path):
        src = tmp_path / "source.backup"
        src.write_bytes(b"test data")
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            result = prepare_serve_file(str(src), "dest.backup")
        assert result == "dest.backup"

    def test_prepare_rejects_traversal(self, tmp_path):
        src = tmp_path / "source.backup"
        src.write_bytes(b"data")
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            with pytest.raises(ValueError, match="path traversal"):
                prepare_serve_file(str(src), "../escape.backup")

    def test_cleanup_removes_file(self, tmp_path):
        serve_dir = tmp_path / "serves"
        serve_dir.mkdir()
        f = serve_dir / "test.backup"
        f.write_bytes(b"data")
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            cleanup_serve_file("test.backup")
        assert not f.exists()

    def test_cleanup_ignores_missing(self, tmp_path):
        with patch("core.backup.file_server.BACKUP_DIR", str(tmp_path)):
            cleanup_serve_file("nonexistent.backup")
