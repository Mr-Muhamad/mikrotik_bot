import logging
import time
from typing import Any

from utils.formatters import sanitize_log_data
from utils.logging_setup import (
    COMPONENT_DATABASE,
    COMPONENT_HANDLER,
    COMPONENT_ROUTER,
    COMPONENT_SERVICE,
    get_request_id,
    get_trace_id,
)

logger = logging.getLogger(__name__)

_DEFAULT_DURATION_WARN_MS = 5000.0


def log_api_call(
    router_key: str,
    command: str,
    duration_ms: float,
    success: bool,
    error: Exception | None = None,
    component: str = COMPONENT_ROUTER,
    response_data: Any | None = None,
) -> None:
    """Log a MikroTik API call with structured fields."""
    extra: dict[str, Any] = {
        "component": component,
        "router_key": router_key,
        "command": command,
        "duration_ms": duration_ms,
        "success": success,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
    }
    if not success and response_data is not None:
        extra["response_data"] = sanitize_log_data(response_data)
    if error is not None:
        extra["error_category"] = _classify_error(error)
    level = logging.ERROR if not success else (
        logging.WARNING if duration_ms > _DEFAULT_DURATION_WARN_MS else logging.INFO
    )
    logger.log(level, "API %s %s %.1fms", "FAILED" if not success else "OK", command, duration_ms, extra=extra)


def log_handler_entry(
    handler_name: str,
    user_id: int | None = None,
    chat_id: int | None = None,
    command_text: str | None = None,
    component: str = COMPONENT_HANDLER,
) -> None:
    """Log entry into a handler with structured fields."""
    extra: dict[str, Any] = {
        "component": component,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
    }
    if user_id is not None:
        extra["user_id"] = user_id
    if chat_id is not None:
        extra["chat_id"] = chat_id
    if command_text is not None:
        extra["command"] = command_text
    logger.info("ENTER %s", handler_name, extra=extra)


def log_handler_exit(
    handler_name: str,
    duration_ms: float,
    success: bool,
    component: str = COMPONENT_HANDLER,
) -> None:
    """Log exit from a handler with structured fields."""
    extra: dict[str, Any] = {
        "component": component,
        "duration_ms": duration_ms,
        "success": success,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
    }
    level = logging.WARNING if not success else logging.INFO
    logger.log(level, "EXIT %s %.1fms", handler_name, duration_ms, extra=extra)


def log_service_call(
    service_name: str,
    operation: str,
    duration_ms: float,
    success: bool,
    error: Exception | None = None,
    component: str = COMPONENT_SERVICE,
) -> None:
    """Log a service-layer call with structured fields."""
    extra: dict[str, Any] = {
        "component": component,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "duration_ms": duration_ms,
        "success": success,
    }
    if error is not None:
        extra["error_category"] = _classify_error(error)
    level = logging.ERROR if not success else logging.INFO
    logger.log(level, "%s.%s %.1fms", service_name, operation, duration_ms, extra=extra)


def log_db_operation(
    operation: str,
    table: str,
    duration_ms: float,
    success: bool,
    error: Exception | None = None,
    component: str = COMPONENT_DATABASE,
) -> None:
    """Log a database operation with structured fields."""
    extra: dict[str, Any] = {
        "component": component,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "duration_ms": duration_ms,
        "success": success,
    }
    if error is not None:
        extra["error_category"] = _classify_error(error)
    level = logging.ERROR if not success else logging.INFO
    logger.log(level, "DB %s.%s %.1fms", operation, table, duration_ms, extra=extra)


def log_router_command(
    router_key: str,
    command: str,
    duration_ms: float,
    success: bool,
    error: Exception | None = None,
) -> None:
    """Log a MikroTik command execution shorthand."""
    log_api_call(router_key, command, duration_ms, success, error, COMPONENT_ROUTER)


def _classify_error(error: Exception) -> str:
    """Quick error category classification for log helpers."""
    from utils.error_response import classify_error

    return classify_error(error)


def timed_operation(
    operation_name: str,
    component: str = COMPONENT_SERVICE,
    **context_fields: Any,
) -> "TimedOperation":
    """Context manager that measures operation duration and logs on exit.

    Usage:
        with timed_operation("backup_userman", router_key="discovered_42"):
            await do_backup()
    """
    return TimedOperation(operation_name, component, **context_fields)


class TimedOperation:
    """Context manager that measures and logs operation duration."""

    def __init__(
        self,
        operation_name: str,
        component: str,
        **context_fields: Any,
    ) -> None:
        self._operation_name = operation_name
        self._component = component
        self._context_fields = context_fields
        self._start: float | None = None
        self._duration_ms: float | None = None

    def __enter__(self) -> "TimedOperation":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        if self._start is None:
            return
        self._duration_ms = (time.monotonic() - self._start) * 1000.0
        success = exc_type is None
        extra: dict[str, Any] = {
            "component": self._component,
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "duration_ms": self._duration_ms,
            "success": success,
        }
        for key, value in self._context_fields.items():
            extra[key] = value
        if exc_type is not None and exc_val is not None:
            extra["error_category"] = _classify_error(exc_val)  # type: ignore[arg-type]
        level = logging.ERROR if not success else logging.INFO
        logger.log(level, "%s %.1fms", self._operation_name, self._duration_ms, extra=extra)