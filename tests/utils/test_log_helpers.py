"""Tests for structured API/service log helpers."""
import logging
import time
from io import StringIO
from unittest.mock import patch

import pytest

from utils.log_helpers import (
    TimedOperation,
    log_api_call,
    log_db_operation,
    log_handler_entry,
    log_handler_exit,
    log_router_command,
    log_service_call,
    timed_operation,
)
from utils.logging_setup import RequestIdFilter, set_request_id
from utils.request_id import request_id_scope


@pytest.fixture(autouse=True)
def _reset_request_id():  # type: ignore[reportUnusedFunction]
    set_request_id("-")
    yield
    set_request_id("-")


class _CaptureFormatter(logging.Formatter):
    """Formatter that appends non-empty extra fields as key=value pairs."""
    _EXTRA_FIELDS = ("request_id", "router_key", "error_category")

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        parts = []
        for key in self._EXTRA_FIELDS:
            val = record.__dict__.get(key)
            if val:
                parts.append(f"{key}={val}")
        if parts:
            msg += " " + " ".join(parts)
        return msg


@pytest.fixture
def capture_log():
    """Attach a StringIO handler at DEBUG to utils.log_helpers for assertions.

    Yields a (logger, stream) tuple so the test can check log records
    via the stream content and/or stored LogRecords.
    """
    logger = logging.getLogger("utils.log_helpers")

    saved_level = logger.level
    saved_handlers = list(logger.handlers)
    saved_filters = list(logger.filters)
    saved_propagate = logger.propagate
    saved_disabled = logger.disabled

    logger.handlers.clear()
    logger.filters.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.disabled = False  # alembic's fileConfig disables unknown loggers

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_CaptureFormatter("%(levelname)s|%(message)s"))
    handler.setLevel(logging.DEBUG)
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)

    yield logger, stream

    logger.removeHandler(handler)
    logger.handlers = saved_handlers
    logger.filters = saved_filters
    logger.setLevel(saved_level)
    logger.propagate = saved_propagate
    logger.disabled = saved_disabled


class TestLogApiCall:
    @pytest.mark.parametrize("duration,success,exp_level", [
        (150.0, True, "INFO"),
        (6000.0, True, "WARNING"),
        (200.0, False, "ERROR"),
    ])
    def test_api_call(self, capture_log, duration, success, exp_level):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with patch("core.metrics.record_mikrotik_request") as mock_metric:
            log_api_call("router_1", "/ip/hotspot/print", duration, success)

        mock_metric.assert_called_once_with("router_1", duration / 1000.0)
        output = stream.getvalue()
        assert output
        assert f"{exp_level}|" in output
        assert "OK" in output if success else "FAILED" in output

    def test_api_call_request_id(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with patch("core.metrics.record_mikrotik_request"):
            with request_id_scope("trace-api-42"):
                log_api_call("r1", "cmd", 10.0, True)

        assert "trace-api-42" in stream.getvalue()

    def test_api_call_includes_error_category(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with patch("core.metrics.record_mikrotik_request"):
            log_api_call("r1", "cmd", 50.0, False, error=ConnectionError("timeout"))

        assert "ERROR" in stream.getvalue()
        assert "error_category=timeout" in stream.getvalue()


class TestLogHandlerEntry:
    def test_entry_with_context(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_handler_entry("start_handler", user_id=123, chat_id=456)

        output = stream.getvalue()
        assert "ENTER start_handler" in output

    def test_entry_minimal(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_handler_entry("simple_handler")
        assert "ENTER simple_handler" in stream.getvalue()


class TestLogHandlerExit:
    def test_exit_success(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_handler_exit("start_handler", 100.0, True)
        assert "EXIT start_handler" in capture_log[1].getvalue()

    def test_exit_failure(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_handler_exit("start_handler", 200.0, False)
        output = stream.getvalue()
        assert "EXIT start_handler" in output
        assert "WARNING" in output


class TestLogServiceCall:
    def test_success(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_service_call("BackupService", "run", 500.0, True)
        assert "BackupService.run" in stream.getvalue()

    def test_failure_with_error(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        log_service_call("BackupService", "run", 500.0, False,
                         error=RuntimeError("backup failed"))
        output = stream.getvalue()
        assert "BackupService.run" in output
        assert "ERROR" in output


class TestLogDbOperation:
    def test_db_operation(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with patch("core.metrics.record_db_query") as mock_metric:
            log_db_operation("SELECT", "routers", 3.0, True)

        mock_metric.assert_called_once_with("SELECT", "routers", True, 3.0)
        assert "DB SELECT.routers" in stream.getvalue()

    def test_db_operation_failure(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with patch("core.metrics.record_db_query"):
            log_db_operation("INSERT", "logs", 10.0, False)
        assert "ERROR" in stream.getvalue()


class TestLogRouterCommand:
    def test_delegates_to_log_api_call(self):
        with patch("utils.log_helpers.log_api_call") as mock:
            log_router_command("router_1", "/system/reboot", 300.0, True)

        mock.assert_called_once_with(
            "router_1", "/system/reboot", 300.0, True, None, "ROUTER"
        )


class TestTimedOperation:
    def test_measures_duration_and_logs(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with timed_operation("test_op", component="service"):
            time.sleep(0.01)

        output = stream.getvalue()
        assert "test_op" in output
        assert "INFO" in output

    def test_logs_error_on_exception(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        try:
            with timed_operation("failing_op", component="service"):
                msg = "something broke"
                raise ValueError(msg)
        except ValueError:
            pass

        output = stream.getvalue()
        assert "failing_op" in output
        assert "ERROR" in output

    def test_context_fields_included(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        with timed_operation(
            "backup_op", component="service", router_key="discovered_1"
        ):
            time.sleep(0.005)

        output = stream.getvalue()
        assert "discovered_1" in output

    def test_manual_class(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        op = TimedOperation("manual_op", "handler")
        op.__enter__()
        time.sleep(0.005)
        op.__exit__(None, None, None)

        assert "manual_op" in stream.getvalue()

    def test_double_enter_no_crash(self, capture_log):  # type: ignore[reportMissingParameterType]
        logger, stream = capture_log  # type: ignore[reportUnusedVariable]
        op = TimedOperation("double", "service")
        op.__enter__()
        op.__enter__()
        op.__exit__(None, None, None)

        assert "double" in stream.getvalue()
