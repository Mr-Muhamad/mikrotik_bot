"""Centralised logging setup with request-id correlation and structured JSON logs.

Provides a ContextVar-based request_id that any handler can set,
and a logging.Filter that injects it into every log record so all
log lines from the same update can be correlated in production logs.

Also configures RotatingFileHandler for production log rotation.
"""

import logging
import logging.handlers
import json
import sys
import io
import os
from uuid import uuid4
from contextlib import contextmanager
from contextvars import ContextVar

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


def _json_serializer(obj):
    if isinstance(obj, (datetime := __import__('datetime'))):
        return datetime.isoformat(obj)
    raise TypeError(f"Type {type(obj).__name__} not JSON serializable")


class JsonFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs for ELK/Loki/Grafana."""

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)

    def format(self, record):
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


def configure_logging(level: int = LOG_LEVEL) -> None:
    """Configure logging with console and rotating file handlers.
    
    Idempotent: can be called multiple times without duplicating handlers/filters.
    Adds RequestIdFilter to root logger and all handlers.
    """
    # Ensure the console stream can emit UTF-8 (emoji, Arabic) on Windows
    # codepages that otherwise raise UnicodeEncodeError in the StreamHandler.
    for _stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(_stream, "reconfigure"):
                cast_stream = _stream
                if isinstance(cast_stream, io.TextIOWrapper):
                    cast_stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    root = logging.getLogger()
    
    # Check if already configured (idempotent)
    has_root_filter = any(isinstance(f, RequestIdFilter) for f in root.filters)
    has_console = any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in root.handlers)
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)
    
    # Add RequestIdFilter to all existing handlers that don't have it
    for handler in root.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())
    
    if has_root_filter and has_console and has_file:
        # Already fully configured - just update handler levels if needed
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
                if handler.level != level:
                    handler.setLevel(level)
        return
    
    # Add RequestIdFilter to root logger (idempotent)
    if not has_root_filter:
        root.addFilter(RequestIdFilter())
    
    # Root logger stays at DEBUG to allow file handler to capture all levels
    if root.level == logging.NOTSET:
        root.setLevel(logging.DEBUG)
    
    # Console handler (human readable)
    if not has_console:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s"
        ))
        console.addFilter(RequestIdFilter())
        root.addHandler(console)
    
    # File handler (JSON, rotating)
    if LOG_FILE and not has_file:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(RequestIdFilter())
        root.addHandler(file_handler)
    
    root.setLevel(logging.DEBUG)
    
    logging.getLogger(__name__).debug("Logging configured - console level: %s, file level: DEBUG", logging.getLevelName(level))

# Create logger instance
logger = logging.getLogger(__name__)