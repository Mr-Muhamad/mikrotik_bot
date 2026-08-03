"""Tests for utils.error_response — extended coverage for classify, format, dispatch, send_text."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from librouteros.exceptions import LibRouterosError
from telegram.error import BadRequest

from utils.error_response import (
    CATEGORY_AUTH,
    CATEGORY_CONNECTION,
    CATEGORY_GENERAL,
    CATEGORY_NOT_FOUND,
    CATEGORY_STORAGE,
    CATEGORY_TIMEOUT,
    _dispatch_message,  # type: ignore[reportPrivateUsage]
    _get_chat_id,  # type: ignore[reportPrivateUsage]
    _sanitize_error_text,  # type: ignore[reportPrivateUsage]
    classify_error,
    format_error_message,
    get_router_key_from_context,
    send_text,
)

# ─── _sanitize_error_text ─────────────────────────────────────


class TestSanitizeErrorText:
    def test_empty_returns_empty(self):
        assert _sanitize_error_text("") == ""

    def test_none_returns_none(self):
        assert _sanitize_error_text(None) is None  # type: ignore[reportArgumentType]

    def test_hides_password_value(self):
        result = _sanitize_error_text("password=secret123456")
        assert "secret123456" not in result
        assert "إخفاء" in result

    def test_hides_bearer_token(self):
        result = _sanitize_error_text("Authorization: Bearer abcdef1234567890")
        assert "abcdef1234567890" not in result

    def test_hides_basic_auth(self):
        result = _sanitize_error_text("Basic dXNlcjpwYXNz")
        assert "dXNlcjpwYXNz" not in result

    def test_short_values_not_hidden(self):
        result = _sanitize_error_text("password=admin")
        # "admin" is only 5 chars, threshold is 6
        assert "admin" in result

    def test_normal_text_unchanged(self):
        assert _sanitize_error_text("no secrets here") == "no secrets here"


# ─── classify_error ──────────────────────────────────────────


class TestClassifyError:
    def test_librouteros_timeout(self):
        err = LibRouterosError("Request timeout from API")
        assert classify_error(err) == CATEGORY_TIMEOUT

    def test_librouteros_refused(self):
        err = LibRouterosError("Connection refused")
        assert classify_error(err) == CATEGORY_CONNECTION

    def test_librouteros_auth(self):
        err = LibRouterosError("invalid password")
        assert classify_error(err) == CATEGORY_AUTH

    def test_librouteros_not_found(self):
        err = LibRouterosError("no such item")
        assert classify_error(err) == CATEGORY_NOT_FOUND

    def test_librouteros_general(self):
        err = LibRouterosError("something weird happened")
        assert classify_error(err) == CATEGORY_GENERAL

    def test_os_error_timeout(self):
        assert classify_error(TimeoutError("timed out")) == CATEGORY_TIMEOUT

    def test_os_error_connection(self):
        assert classify_error(ConnectionError("connection reset")) == CATEGORY_CONNECTION

    def test_os_error_storage(self):
        assert classify_error(OSError("no space left on device")) == CATEGORY_STORAGE

    def test_value_error_not_found(self):
        assert classify_error(ValueError("item not found")) == CATEGORY_NOT_FOUND

    def test_unknown_error_returns_general(self):
        assert classify_error(RuntimeError("boom")) == CATEGORY_GENERAL


# ─── format_error_message ─────────────────────────────────────


class TestFormatErrorMessage:
    @patch("utils.logging_setup.get_request_id", return_value=None)
    def test_general_category_includes_error_text(self, _mock_req):  # type: ignore[reportMissingParameterType]
        msg = format_error_message(RuntimeError("something broke"))
        assert "حدث خطأ" in msg
        assert "something broke" in msg

    @patch("utils.logging_setup.get_request_id", return_value=None)
    def test_connection_category(self, _mock_req):  # type: ignore[reportMissingParameterType]
        err = LibRouterosError("Connection refused")
        msg = format_error_message(err)
        assert "الاتصال بالروتر" in msg

    @patch("utils.logging_setup.get_request_id", return_value=None)
    def test_with_router_key(self, _mock_req):  # type: ignore[reportMissingParameterType]
        msg = format_error_message(RuntimeError("err"), router_key="discovered_1")
        assert "discovered_1" in msg

    @patch("utils.logging_setup.get_request_id", return_value="abc123")
    def test_with_request_id(self, _mock_req):  # type: ignore[reportMissingParameterType]
        msg = format_error_message(RuntimeError("err"))
        assert "abc123" in msg


# ─── _get_chat_id ─────────────────────────────────────────────


class TestGetChatId:
    def test_none_update(self):
        assert _get_chat_id(None) is None

    def test_callback_query_chat_id(self):
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 42
        update.effective_message = None
        update.effective_chat = None
        assert _get_chat_id(update) == 42

    def test_effective_message_chat_id(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = MagicMock()
        update.effective_message.chat_id = 99
        update.effective_chat = None
        assert _get_chat_id(update) == 99

    def test_effective_chat_id(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = MagicMock()
        update.effective_chat.id = 77
        assert _get_chat_id(update) == 77

    def test_no_sources_returns_none(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = None
        assert _get_chat_id(update) is None


# ─── get_router_key_from_context ──────────────────────────────


class TestGetRouterKeyFromContext:
    def test_none_context(self):
        assert get_router_key_from_context(None) is None
        assert get_router_key_from_context(None, default="fallback") == "fallback"

    def test_no_user_data(self):
        ctx = MagicMock(spec=[])  # no user_data attr
        assert get_router_key_from_context(ctx) is None

    def test_selected_router(self):
        ctx = MagicMock()
        ctx.user_data = {"selected_router": "r1"}
        assert get_router_key_from_context(ctx) == "r1"

    def test_router_key_fallback(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "r2"}
        assert get_router_key_from_context(ctx) == "r2"

    def test_empty_string_returns_default(self):
        ctx = MagicMock()
        ctx.user_data = {"selected_router": ""}
        assert get_router_key_from_context(ctx, default="def") == "def"

    def test_non_string_returns_default(self):
        ctx = MagicMock()
        ctx.user_data = {"selected_router": 123}
        assert get_router_key_from_context(ctx, default="def") == "def"


# ─── send_text ────────────────────────────────────────────────


class TestSendText:
    @pytest.mark.asyncio
    async def test_sends_via_bot(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = MagicMock()
        update.effective_chat.id = 10
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=100))
        await send_text(update, ctx, "hello")
        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_chat_id_does_nothing(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = None
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()
        await send_text(update, ctx, "hello")
        ctx.bot.send_message.assert_not_awaited()


# ─── _dispatch_message ────────────────────────────────────────


class TestDispatchMessage:
    @pytest.mark.asyncio
    async def test_benign_error_in_dispatch_ignored(self):
        update = MagicMock()
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(
            side_effect=BadRequest("Message is not modified")
        )
        update.callback_query = query
        update.effective_message = None
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()
        # Should not raise
        await _dispatch_message(update, ctx, "text", None, 1, "label")
