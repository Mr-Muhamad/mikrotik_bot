"""Centralised logging setup with request-id correlation, component tagging,
and structured JSON logs.

Provides ContextVar-based request_id, component, and trace_id that any handler
or service can set, and a logging.Filter that injects them into every log
record so all lines from the same logical flow can be correlated.

Also configures RotatingFileHandler for production log rotation.
"""

import io
import json
import logging
import logging.handlers
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime
from typing import Any, Generator
from uuid import uuid4

# Production configuration from environment
def _parse_log_level(raw: str | None) -> int:
    """Parse LOG_LEVEL env var accepting either a numeric level or a name (e.g. "DEBUG")."""
    if not raw:
        return logging.INFO
    try:
        return int(raw)
    except ValueError:
        return getattr(logging, raw.upper(), logging.INFO)


LOG_LEVEL = _parse_log_level(os.getenv("LOG_LEVEL"))
LOG_FILE = os.getenv("LOG_FILE", "logs/mikrotik-bot.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "30"))

# ── Component tags ────────────────────────────────────────────────────────

COMPONENT_HANDLER = "HANDLER"
COMPONENT_ROUTER = "ROUTER"
COMPONENT_SERVICE = "SERVICE"
COMPONENT_DATABASE = "DATABASE"
COMPONENT_TELEGRAM = "TELEGRAM"
COMPONENT_SYSTEM = "SYSTEM"
COMPONENT_BACKUP = "BACKUP"
COMPONENT_METRICS = "METRICS"


_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_component_var: ContextVar[str] = ContextVar("component", default="-")
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
_user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
_chat_id_var: ContextVar[int | None] = ContextVar("chat_id", default=None)
_router_key_var: ContextVar[str | None] = ContextVar("router_key", default=None)
_command_var: ContextVar[str | None] = ContextVar("command", default=None)
_success_var: ContextVar[bool | None] = ContextVar("success", default=None)
_duration_ms_var: ContextVar[float | None] = ContextVar("duration_ms", default=None)
_error_category_var: ContextVar[str | None] = ContextVar("error_category", default=None)


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def new_request_id() -> str:
    return uuid4().hex[:12]


def get_component() -> str:
    return _component_var.get()


def set_component(component: str) -> None:
    _component_var.set(component)


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def new_trace_id() -> str:
    return uuid4().hex[:12]


def get_user_id() -> int | None:
    return _user_id_var.get()


def set_user_id(user_id: int | None) -> None:
    _user_id_var.set(user_id)


def get_chat_id() -> int | None:
    return _chat_id_var.get()


def set_chat_id(chat_id: int | None) -> None:
    _chat_id_var.set(chat_id)


def get_router_key() -> str | None:
    return _router_key_var.get()


def set_router_key(router_key: str | None) -> None:
    _router_key_var.set(router_key)


def get_command() -> str | None:
    return _command_var.get()


def set_command(command: str | None) -> None:
    _command_var.set(command)


def get_success() -> bool | None:
    return _success_var.get()


def set_success(success: bool | None) -> None:
    _success_var.set(success)


def get_duration_ms() -> float | None:
    return _duration_ms_var.get()


def set_duration_ms(duration_ms: float | None) -> None:
    _duration_ms_var.set(duration_ms)


def get_error_category() -> str | None:
    return _error_category_var.get()


def set_error_category(error_category: str | None) -> None:
    _error_category_var.set(error_category)


@contextmanager
def bind_component(component: str):
    """Context manager that sets the component tag for the duration of the block."""
    token = _component_var.set(component)
    try:
        yield
    finally:
        _component_var.reset(token)


@contextmanager
def bind_trace_id(trace_id: str):
    """Context manager that sets the trace id for the duration of the block."""
    token = _trace_id_var.set(trace_id)
    try:
        yield
    finally:
        _trace_id_var.reset(token)


def _bind_context_values(
    bindings: list[tuple[ContextVar[Any], object]],
) -> list[Token[Any]]:
    """Bind non-None context values, returning their tokens for later reset."""
    tokens: list[Token[Any]] = []
    for var, value in bindings:
        if value is not None:
            tokens.append(var.set(value))
    return tokens


@contextmanager
def bind_context(
    request_id: str | None = None,
    component: str | None = None,
    trace_id: str | None = None,
    user_id: int | None = None,
    chat_id: int | None = None,
    router_key: str | None = None,
    command: str | None = None,
    success: bool | None = None,
    duration_ms: float | None = None,
    error_category: str | None = None,
) -> Generator[None, Any, None]:
    """Bind multiple context values for the duration of the block."""
    tokens = _bind_context_values(
        [
            (_request_id_var, request_id),
            (_component_var, component),
            (_trace_id_var, trace_id),
            (_user_id_var, user_id),
            (_chat_id_var, chat_id),
            (_router_key_var, router_key),
            (_command_var, command),
            (_success_var, success),
            (_duration_ms_var, duration_ms),
            (_error_category_var, error_category),
        ]
    )
    try:
        yield
    finally:
        for token in tokens:
            token.var.reset(token)


@contextmanager
def bind_log_context(
    *,
    component: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    user_id: int | None = None,
    chat_id: int | None = None,
    router_key: str | None = None,
    command: str | None = None,
) -> Generator[None, Any, None]:
    """Lightweight context binding for structured log fields.

    Only binds the fields that are explicitly provided (non-None), leaving
    all other ContextVars unchanged.
    """
    tokens = _bind_context_values(
        [
            (_component_var, component),
            (_request_id_var, request_id),
            (_trace_id_var, trace_id),
            (_user_id_var, user_id),
            (_chat_id_var, chat_id),
            (_router_key_var, router_key),
            (_command_var, command),
        ]
    )
    try:
        yield
    finally:
        for token in tokens:
            token.var.reset(token)


def _json_serializer(obj: object) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj).__name__} not JSON serializable")


class JsonFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs for ELK/Loki/Grafana."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "component": getattr(record, "component", "-"),
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stacktrace"] = self.formatStack(record.stack_info)
        # Add optional structured fields if present
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_entry["duration_ms"] = round(duration_ms, 2)
        success = getattr(record, "success", None)
        if success is not None:
            log_entry["success"] = success
        router_key = getattr(record, "router_key", None)
        if router_key is not None:
            log_entry["router_key"] = router_key
        user_id = getattr(record, "user_id", None)
        if user_id is not None:
            log_entry["user_id"] = user_id
        chat_id = getattr(record, "chat_id", None)
        if chat_id is not None:
            log_entry["chat_id"] = chat_id
        command = getattr(record, "command", None)
        if command is not None:
            log_entry["command"] = command
        error_category = getattr(record, "error_category", None)
        if error_category is not None:
            log_entry["error_category"] = error_category
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
    """Inject the current request_id, component, and trace_id into every log record.

    Records gain `request_id`, `component`, and `trace_id` attributes that
    formatters can reference. When no value is bound the placeholder `-` is used.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        record.component = _component_var.get()
        record.trace_id = _trace_id_var.get()
        return True


def _ensure_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 so emoji/Arabic don't crash."""
    for _stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(_stream, "reconfigure"):
                cast_stream = _stream
                if isinstance(cast_stream, io.TextIOWrapper):
                    cast_stream.reconfigure(encoding="utf-8")
        except OSError:
            logger.debug("Failed to reconfigure stream encoding to utf-8")


class _FlushStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]  # StreamHandler is generic in Python 3.13+
    """StreamHandler that flushes after every record.

    Ensures log lines appear immediately in the terminal even when stdout is
    buffered (common on Windows with cmd.exe or some IDEs).
    """

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def _add_console_handler(root: logging.Logger, level: int) -> None:
    """Attach a human-readable console handler to *root*."""
    console = _FlushStreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] [%(component)s] - %(message)s")
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

    has_console = any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in root.handlers)
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)

    if has_console and has_file:
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout and handler.level != level:
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
