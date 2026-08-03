"""Tests for utils.request_id — context scope and update binding decorator."""

import logging
from unittest.mock import MagicMock

import pytest

from utils import request_id
from utils.logging_setup import _request_id_var  # type: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _reset_request_id():  # type: ignore[reportUnusedFunction]
    _request_id_var.set("-")
    yield
    _request_id_var.set("-")


# ─── request_id_scope tests ────────────────────────────────────


class TestRequestIdScope:
    def test_sets_and_resets(self):
        assert _request_id_var.get() == "-"
        with request_id.request_id_scope("abc123"):
            assert _request_id_var.get() == "abc123"
        # After scope exits, reset to default
        assert _request_id_var.get() == "-"

    def test_resets_on_exception(self):
        with pytest.raises(RuntimeError):
            with request_id.request_id_scope("xyz"):
                assert _request_id_var.get() == "xyz"
                raise RuntimeError("boom")
        assert _request_id_var.get() == "-"

    def test_nested_scopes(self):
        with request_id.request_id_scope("outer"):
            assert _request_id_var.get() == "outer"
            with request_id.request_id_scope("inner"):
                assert _request_id_var.get() == "inner"
            assert _request_id_var.get() == "outer"
        assert _request_id_var.get() == "-"


# ─── bind_request_id_from_update tests ─────────────────────────


class TestBindRequestIdDecorator:
    @pytest.mark.asyncio
    async def test_binds_update_id_to_context(self):
        captured = []

        @request_id.bind_request_id_from_update
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            captured.append(_request_id_var.get())
            return "ok"

        u = MagicMock()
        u.update_id = 12345
        await handler(u, MagicMock())
        assert captured[0] == "12345"
        # After handler, context is reset
        assert _request_id_var.get() == "-"

    @pytest.mark.asyncio
    async def test_missing_update_id_defaults_to_dash(self):
        captured = []

        @request_id.bind_request_id_from_update
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            captured.append(_request_id_var.get())
            return "ok"

        u = MagicMock(spec=[])  # no update_id attribute
        await handler(u, MagicMock())
        assert captured[0] == "-"

    @pytest.mark.asyncio
    async def test_logs_carry_request_id(self, caplog):  # type: ignore[reportMissingParameterType]
        log = logging.getLogger("test_request_id_bind")

        @request_id.bind_request_id_from_update
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            log.info("work happening")
            return "ok"

        # Attach request_id filter to test logger
        from utils.logging_setup import RequestIdFilter

        log.addFilter(RequestIdFilter())
        log.setLevel(logging.INFO)

        u = MagicMock()
        u.update_id = 99999
        with caplog.at_level(logging.INFO, logger="test_request_id_bind"):
            await handler(u, MagicMock())

        assert any("work happening" in r.message for r in caplog.records)
        record = next(r for r in caplog.records if "work happening" in r.message)
        assert getattr(record, "request_id", "-") == "99999"

    @pytest.mark.asyncio
    async def test_passes_args_kwargs_through(self):
        @request_id.bind_request_id_from_update
        async def handler(update, context, *args, **kwargs):  # type: ignore[reportMissingParameterType]
            return (args, kwargs)

        u = MagicMock()
        u.update_id = 1
        result = await handler(u, MagicMock(), "extra", foo="bar")
        assert result == (("extra",), {"foo": "bar"})

    @pytest.mark.asyncio
    async def test_isolated_per_call(self):
        captured = []

        @request_id.bind_request_id_from_update
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            captured.append(_request_id_var.get())
            return "ok"

        u1 = MagicMock()
        u1.update_id = 111
        u2 = MagicMock()
        u2.update_id = 222
        await handler(u1, MagicMock())
        await handler(u2, MagicMock())
        assert captured == ["111", "222"]
