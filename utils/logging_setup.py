"""Centralised logging setup with request-id correlation and structured JSON logs.

Provides a ContextVar-based request_id that any handler can set,
and a logging.Filter that injects it into every log record so all
log lines from the same update can be correlated in production logs.

Also configures RotatingFileHandler for production log rotation.
"""

import io
import json
import logging
import logging.handlers
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

# Production configuration from environment
LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO))
LOG_FILE = os.getenv("LOG_FILE", "logs/mikrotik-bot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "30"))

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def new_request_id() -> str:
    return uuid4().hex[:12]


def _json_serializer(obj: object) -> str:
    if isinstance(obj, (datetime := __import__("datetime"))):
        return datetime.isoformat(obj)
    raise TypeError(f"Type {type(obj).__name__} not JSON serializable")


class JsonFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs for ELK/Loki/Grafana."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stacktrace"] = self.formatStack(record.stack_info)
        return json.dumps(log_entry, default=_json_serializer)


@contextmanager
def bind_request_id(request_id: str):
    """Context manager that sets the request id for the duration of the block."""
    token = _request_id_var.set(request_id)
    try:
        yield
    finally:
        _request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every log record.

    Records gain a `request_id` attribute that formatters can reference.
    When no request_id is bound, the placeholder `-` is used.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


def _ensure_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 so emoji/Arabic don't crash."""
    for _stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(_stream, "reconfigure"):
                cast_stream = _stream
                if isinstance(cast_stream, io.TextIOWrapper):
                    cast_stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _add_console_handler(root: logging.Logger, level: int) -> None:
    """Attach a human-readable console handler to *root*."""
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s")
    )
    console.addFilter(RequestIdFilter())
    root.addHandler(console)


def _add_file_handler(root: logging.Logger) -> None:
    """Attach a rotating JSON file handler to *root*."""
    if not LOG_FILE:
        return
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(RequestIdFilter())
    root.addHandler(file_handler)


def _ensure_request_id_filter(root: logging.Logger) -> None:
    """Ensure ``RequestIdFilter`` is present on the root logger and every handler."""
    if not any(isinstance(f, RequestIdFilter) for f in root.filters):
        root.addFilter(RequestIdFilter())
    for handler in root.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())


def configure_logging(level: int = LOG_LEVEL) -> None:
    """Configure logging with console and rotating file handlers.

    Idempotent: can be called multiple times without duplicating handlers/filters.
    Adds RequestIdFilter to root logger and all handlers.
    """
    _ensure_utf8_streams()
    root = logging.getLogger()
    _ensure_request_id_filter(root)

    has_console = any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in root.handlers
    )
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)

    if has_console and has_file:
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
                if handler.level != level:
                    handler.setLevel(level)
        return

    if root.level == logging.NOTSET:
        root.setLevel(logging.DEBUG)

    if not has_console:
        _add_console_handler(root, level)

    if not has_file:
        _add_file_handler(root)

    root.setLevel(logging.DEBUG)

    logging.getLogger(__name__).debug(
        "Logging configured - console level: %s, file level: DEBUG",
        logging.getLevelName(level),
    )


# Create logger instance
logger = logging.getLogger(__name__)
