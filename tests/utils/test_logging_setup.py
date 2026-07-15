"""Tests for the request-id tracking utilities."""

import logging
from io import StringIO


from utils.logging_setup import (
    RequestIdFilter,
    configure_logging,
    get_request_id,
    new_request_id,
    set_request_id,
)


class TestRequestIdContext:
    def teardown_method(self):
        set_request_id("-")

    def test_default_request_id_is_dash(self):
        set_request_id("-")
        assert get_request_id() == "-"

    def test_set_and_get(self):
        set_request_id("abc123")
        assert get_request_id() == "abc123"

    def test_new_request_id_unique(self):
        ids = {new_request_id() for _ in range(100)}
        assert len(ids) == 100
        for rid in ids:
            assert len(rid) == 12

    def test_bind_request_id_resets(self):
        set_request_id("-")
        from utils.request_id import request_id_scope
        with request_id_scope("scope-id"):
            assert get_request_id() == "scope-id"
        assert get_request_id() == "-"


class TestRequestIdFilter:
    def test_filter_injects_request_id(self):
        set_request_id("hello")
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="", lineno=0,
            msg="msg", args=(), exc_info=None,
        )
        f = RequestIdFilter()
        f.filter(record)
        assert record.request_id == "hello"

    def test_filter_default_dash(self):
        set_request_id("-")
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="", lineno=0,
            msg="msg", args=(), exc_info=None,
        )
        f = RequestIdFilter()
        f.filter(record)
        assert record.request_id == "-"


class TestConfigureLogging:
    def test_attach_filter(self):
        root = logging.getLogger()
        for f in list(root.filters):
            if isinstance(f, RequestIdFilter):
                root.removeFilter(f)
        configure_logging()
        assert any(isinstance(f, RequestIdFilter) for f in root.filters)

    def test_attach_filter_to_handlers(self):
        root = logging.getLogger()
        handler = logging.NullHandler()
        for f in list(handler.filters):
            if isinstance(f, RequestIdFilter):
                handler.removeFilter(f)
        root.addHandler(handler)
        try:
            configure_logging()
            assert any(isinstance(f, RequestIdFilter) for f in handler.filters)
        finally:
            root.removeHandler(handler)

    def test_idempotent(self):
        root = logging.getLogger()
        for f in list(root.filters):
            if isinstance(f, RequestIdFilter):
                root.removeFilter(f)
        configure_logging()
        configure_logging()
        count = sum(1 for f in root.filters if isinstance(f, RequestIdFilter))
        assert count == 1

    def test_handler_filter_injects_id_for_child_logger(self):
        """Child loggers (e.g. apscheduler) propagate to root handlers —
        the handler filter must inject request_id so the format string
        does not raise KeyError.
        """
        captured = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(getattr(record, "request_id", "<MISSING>"))

        root = logging.getLogger()
        saved_handlers = list(root.handlers)
        saved_filters = list(root.filters)
        saved_level = root.level
        capture = CaptureHandler()
        capture.setLevel(logging.DEBUG)
        root.addHandler(capture)
        root.setLevel(logging.DEBUG)
        try:
            configure_logging()
            set_request_id("trace-XYZ")
            child = logging.getLogger("apscheduler.fake")
            child.setLevel(logging.DEBUG)
            child.propagate = True
            child.info("ping")
        finally:
            set_request_id("-")
            root.removeHandler(capture)
            root.handlers = saved_handlers
            root.filters = saved_filters
            root.setLevel(saved_level)

        assert captured == ["trace-XYZ"]


class TestRequestIdInRealLog:
    def test_log_record_carries_request_id(self):
        logger = logging.getLogger("test.request_id")
        for h in list(logger.handlers):
            logger.removeHandler(h)
        for f in list(logger.filters):
            if isinstance(f, RequestIdFilter):
                logger.removeFilter(f)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("[%(request_id)s] %(message)s"))
        logger.addHandler(handler)
        logger.addFilter(RequestIdFilter())
        logger.setLevel(logging.INFO)

        set_request_id("trace-001")
        logger.info("hello")

        output = stream.getvalue()
        assert "[trace-001]" in output
        assert "hello" in output
