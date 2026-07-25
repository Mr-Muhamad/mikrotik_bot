"""HTTP file-transfer server replacing plaintext FTP for router ↔ bot file exchange.

RouterOS pushes files to the bot via ``/tool/fetch upload=yes`` (POST /upload).
The bot serves files to routers via ``/tool/fetch`` (GET /files/<name>).

No SSL — this server must run inside an isolated management network only.
"""

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from config import BACKUP_DIR, FILE_SERVER_PORT, FILE_SERVER_SECRET

logger = logging.getLogger(__name__)

# Allow-listed file extensions the router may push to us.
_ALLOWED_EXTENSIONS = (".backup", ".rsc", ".umb", ".tar")

# Maximum upload size: 100 MB
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024

_server: HTTPServer | None = None
_server_thread: threading.Thread | None = None


class _FileRequestHandler(BaseHTTPRequestHandler):
    """Handle POST /upload (receive from router) and GET /files/<name> (serve to router)."""

    def log_message(self, format: str, *args: object) -> None:
        logger.debug(f"FileServer: {format % args}")

    # ── Authentication ───────────────────────────────────────
    def _check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {FILE_SERVER_SECRET}":
            return True
        self.send_error(401, "Unauthorized")
        return False

    # ── POST /upload — router pushes a file to the bot ──────
    def do_POST(self) -> None:
        if self.path != "/upload":
            self.send_error(404)
            return
        if not self._check_auth():
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > _MAX_UPLOAD_BYTES:
            self.send_error(413, "File too large")
            return

        filename = self.headers.get("X-Filename", "")
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            self.send_error(400, "Invalid filename")
            return
        if not filename.endswith(_ALLOWED_EXTENSIONS):
            self.send_error(400, "Extension not allowed")
            return

        router_key = self.headers.get("X-Router-Key", "unknown")

        body = self.rfile.read(content_length)
        upload_dir = os.path.join(BACKUP_DIR, "uploads", router_key)
        os.makedirs(upload_dir, exist_ok=True)
        dest = os.path.join(upload_dir, filename)

        # Prevent path traversal (belt-and-suspenders)
        if os.path.abspath(dest) != os.path.abspath(os.path.join(upload_dir, filename)):
            self.send_error(400, "Path traversal blocked")
            return

        with open(dest, "wb") as fh:
            fh.write(body)

        logger.info(f"FileServer: received {filename} ({len(body)} bytes) from {router_key}")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    # ── GET /files/<name> — serve a file to the router ──────
    def do_GET(self) -> None:
        if not self.path.startswith("/files/"):
            self.send_error(404)
            return
        if not self._check_auth():
            return

        filename = self.path[len("/files/") :]
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            self.send_error(400, "Invalid filename")
            return

        # Search in upload_dir first (files the bot placed for the router)
        upload_dir = os.path.join(BACKUP_DIR, "serves")
        target = os.path.join(upload_dir, filename)

        if not os.path.isfile(target):
            self.send_error(404, "File not found")
            return

        file_size = os.path.getsize(target)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()

        with open(target, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

        logger.info(f"FileServer: served {filename} ({file_size} bytes)")


def start_file_server() -> None:
    """Start the file server in a daemon thread. Safe to call multiple times."""
    global _server, _server_thread
    if _server is not None:
        return

    _server = HTTPServer(("0.0.0.0", FILE_SERVER_PORT), _FileRequestHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    logger.info(f"File server started on port {FILE_SERVER_PORT}")


def stop_file_server() -> None:
    """Shut down the file server gracefully."""
    global _server, _server_thread
    if _server is not None:
        _server.shutdown()
        _server = None
        _server_thread = None
        logger.info("File server stopped")


def prepare_serve_file(local_path: str, filename: str) -> str:
    """Stage a local file for the router to download via GET /files/<filename>.

    Returns the filename to use in the /tool/fetch URL.
    """
    serve_dir = os.path.join(BACKUP_DIR, "serves")
    os.makedirs(serve_dir, exist_ok=True)
    dest = os.path.join(serve_dir, filename)
    if os.path.abspath(dest) != os.path.join(serve_dir, filename):
        raise ValueError("Filename contains path traversal")
    import shutil

    shutil.copy2(local_path, dest)
    return filename


def cleanup_serve_file(filename: str) -> None:
    """Remove a staged file after the router has fetched it."""
    path = os.path.join(BACKUP_DIR, "serves", filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as e:
        logger.warning(f"Failed to cleanup serve file {filename}: {e}")
