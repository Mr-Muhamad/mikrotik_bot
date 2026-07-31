"""Tests for utils.error_response benign-error handling and chat_cleaner safe edits."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from librouteros.exceptions import LibRouterosError
from telegram import Chat, Message
from telegram.error import BadRequest

from utils.chat_cleaner import edit_clean, safe_edit_plain
from utils.error_response import (
    CATEGORY_AUTH,
    CATEGORY_CONNECTION,
    CATEGORY_GENERAL,
    CATEGORY_NOT_FOUND,
    CATEGORY_STORAGE,
    CATEGORY_TIMEOUT,
    _classify_librouteros,
    _classify_os_error,
    _get_chat_id,
    classify_error,
    format_error_message,
    get_router_key_from_context,
    is_benign_telegram_error,
    log_error,
    send_error,
    send_text,
)
from utils.logging_setup import set_request_id


def _ctx(chat_id: int = 1, user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = {}
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=100))
    return ctx


def _callback_update(chat_id: int = 1, edit_raises=None):
    update = MagicMock()
    update.effective_message = None
    update.effective_chat = None
    query = MagicMock()
    query.message = MagicMock()
    query.message.chat_id = chat_id
    query.message.message_id = 60
    if edit_raises is None:
        query.edit_message_text = AsyncMock(
            return_value=Message(
                message_id=61,
                date=datetime.datetime.now(datetime.UTC),
                chat=Chat(id=chat_id, type="private"),
            )
        )
    else:
        query.edit_message_text = AsyncMock(side_effect=edit_raises)
    update.callback_query = query
    return update


# ─── is_benign_telegram_error ───────────────────────────────────


class TestIsBenignTelegramError:
    def test_modified(self):
        assert is_benign_telegram_error(BadRequest("Message is not modified")) is True

    def test_not_found(self):
        assert is_benign_telegram_error(BadRequest("Message to edit not found")) is True

    def test_exactly_same(self):
        assert is_benign_telegram_error(BadRequest("message is exactly the same content")) is True

    def test_other_badrequest_not_benign(self):
        assert is_benign_telegram_error(BadRequest("can't parse entities")) is False

    def test_non_badrequest_not_benign(self):
        assert is_benign_telegram_error(ValueError("boom")) is False


# ─── _classify_librouteros ──────────────────────────────────────


class TestClassifyLibrouteros:
    def test_timeout(self):
        assert _classify_librouteros(LibRouterosError("connection timeout")) == CATEGORY_TIMEOUT

    def test_connection_refused(self):
        assert _classify_librouteros(LibRouterosError("connection refused")) == CATEGORY_CONNECTION

    def test_auth_failure(self):
        assert _classify_librouteros(LibRouterosError("invalid password")) == CATEGORY_AUTH

    def test_not_found(self):
        assert _classify_librouteros(LibRouterosError("no such resource")) == CATEGORY_NOT_FOUND

    def test_general(self):
        assert _classify_librouteros(LibRouterosError("unexpected error")) == CATEGORY_GENERAL


# ─── _classify_os_error ─────────────────────────────────────────


class TestClassifyOsError:
    def test_timeout(self):
        assert _classify_os_error(TimeoutError("timed out")) == CATEGORY_TIMEOUT

    def test_storage(self):
        assert _classify_os_error(OSError("disk full")) == CATEGORY_STORAGE

    def test_connection_default(self):
        assert _classify_os_error(ConnectionError("reset")) == CATEGORY_CONNECTION


# ─── classify_error ─────────────────────────────────────────────


class TestClassifyError:
    def test_librouteros_timeout(self):
        assert classify_error(LibRouterosError("timeout")) == CATEGORY_TIMEOUT

    def test_oserror_connection(self):
        assert classify_error(OSError("broken pipe")) == CATEGORY_CONNECTION

    def test_valueerror_not_found(self):
        assert classify_error(ValueError("router not found")) == CATEGORY_NOT_FOUND

    def test_valueerror_other_is_general(self):
        assert classify_error(ValueError("bad value")) == CATEGORY_GENERAL

    def test_httpx_timeout(self):
        assert classify_error(httpx.TimeoutException("request timed out")) == CATEGORY_TIMEOUT

    def test_httpx_connect_error(self):
        assert classify_error(httpx.ConnectError("connection failed")) == CATEGORY_CONNECTION

    def test_httpx_unavailable(self):
        with patch.dict("sys.modules", {"httpx": None}):
            assert classify_error(ValueError("no httpx")) == CATEGORY_GENERAL

    def test_general_exception(self):
        assert classify_error(RuntimeError("unexpected")) == CATEGORY_GENERAL


# ─── log_error ──────────────────────────────────────────────────


class TestLogError:
    @patch("utils.error_response.logger.error")
    def test_logs_without_context(self, mock_error):
        log_error(ValueError("test"))
        assert mock_error.call_count == 1

    @patch("utils.error_response.logger.error")
    def test_logs_with_context(self, mock_error):
        from utils.error_response import ErrorContext

        ctx = ErrorContext(
            router_key="router1",
            command="/test",
            user_id=123,
            chat_id=456,
            attempt=2,
            duration_ms=150.0,
        )
        log_error(ValueError("test"), context=ctx)
        assert mock_error.call_count == 1


# ─── format_error_message ───────────────────────────────────────


class TestFormatErrorMessage:
    def test_general_category_includes_error(self):
        msg = format_error_message(ValueError("something broke"), router_key="r1")
        self = msg  # noqa
        assert "something broke" in msg
        assert "r1" in msg

    def test_connection_no_error_details(self):
        msg = format_error_message(LibRouterosError("connection refused"), router_key="r1")
        assert "connection refused" not in msg
        assert "r1" in msg

    def test_router_key_none_omits_id(self):
        msg = format_error_message(ValueError("broke"))
        assert "🆔" not in msg

    def test_request_id_included_when_present(self):
        set_request_id("req-abc")
        try:
            msg = format_error_message(ValueError("broke"))
            assert "req-abc" in msg
        finally:
            set_request_id("-")

    def test_request_id_dash_omitted(self):
        set_request_id("-")
        msg = format_error_message(ValueError("broke"))
        assert "#" not in msg


# ─── send_error benign handling ─────────────────────────────────


class TestSendErrorBenign:
    @pytest.mark.asyncio
    @patch("utils.error_response.logger.debug")
    async def test_benign_logged_debug_and_no_user_message(self, mock_debug):
        update = _callback_update()
        ctx = _ctx()
        error = BadRequest("Message is not modified")
        await send_error(update, ctx, error)
        update.callback_query.edit_message_text.assert_not_called()
        ctx.bot.send_message.assert_not_called()
        assert mock_debug.call_count == 1
        log_msg = mock_debug.call_args[0][0]
        assert "Benign" in log_msg

    @pytest.mark.asyncio
    async def test_real_error_still_dispatches(self):
        update = _callback_update()
        ctx = _ctx()
        error = ValueError("real failure")
        await send_error(update, ctx, error)
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("utils.error_response.logger.error")
    async def test_send_error_with_error_context(self, mock_error):
        from utils.error_response import ErrorContext

        update = _callback_update()
        ctx = _ctx()
        error = ValueError("context error")
        ectx = ErrorContext(command="/test", user_id=123, chat_id=456, duration_ms=50.0)
        await send_error(update, ctx, error, error_context=ectx)
        update.callback_query.edit_message_text.assert_awaited_once()


# ─── send_text ──────────────────────────────────────────────────


class TestSendText:
    @pytest.mark.asyncio
    async def test_send_text_with_chat_id(self):
        update = _callback_update()
        ctx = _ctx()
        await send_text(update, ctx, "hello", chat_id=99)
        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_text_no_target(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = None
        ctx = _ctx()
        await send_text(update, ctx, "hello")
        ctx.bot.send_message.assert_not_called()


# ─── _get_chat_id ───────────────────────────────────────────────


class TestGetChatId:
    def test_update_none(self):
        assert _get_chat_id(None) is None

    def test_no_callback_no_message(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = None
        assert _get_chat_id(update) is None

    def test_effective_message(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = MagicMock(chat_id=777)
        update.effective_chat = None
        assert _get_chat_id(update) == 777

    def test_effective_chat(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = MagicMock(id=888)
        assert _get_chat_id(update) == 888


# ─── get_router_key_from_context ────────────────────────────────


class TestGetRouterKeyFromContext:
    def test_none_context_returns_default(self):
        assert get_router_key_from_context(None, default="def") == "def"

    def test_no_user_data_returns_default(self):
        ctx = MagicMock(spec=[])
        assert get_router_key_from_context(ctx, default="def") == "def"

    def test_selected_router_returns_key(self):
        ctx = MagicMock(user_data={"selected_router": "r2"})
        assert get_router_key_from_context(ctx) == "r2"

    def test_router_key_fallback(self):
        ctx = MagicMock(user_data={"router_key": "r3"})
        assert get_router_key_from_context(ctx) == "r3"


# ─── _dispatch_message paths ────────────────────────────────────


class TestDispatchMessage:
    @pytest.mark.asyncio
    async def test_effective_message_reply(self):
        update = MagicMock()
        update.callback_query = None
        effective = MagicMock()
        effective.reply_text = AsyncMock(return_value=MagicMock(message_id=200))
        effective.chat_id = 1
        update.effective_message = effective
        ctx = _ctx()
        from utils.error_response import _dispatch_message

        await _dispatch_message(update, ctx, "hi", None, 1, "test")
        effective.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_send_message(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        ctx = _ctx()
        from utils.error_response import _dispatch_message

        await _dispatch_message(update, ctx, "hi", None, 5, "test")
        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("utils.error_response.logger.debug")
    async def test_benign_telegram_error_ignored(self, mock_debug):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        ctx = _ctx()
        ctx.bot.send_message = AsyncMock(side_effect=BadRequest("Message is not modified"))
        from utils.error_response import _dispatch_message

        await _dispatch_message(update, ctx, "hi", None, 5, "test")
        mock_debug.assert_called()

    @pytest.mark.asyncio
    @patch("utils.error_response.logger.error")
    async def test_non_benign_telegram_error_logged(self, mock_error):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        ctx = _ctx()
        ctx.bot.send_message = AsyncMock(side_effect=BadRequest("can't parse entities"))
        from utils.error_response import _dispatch_message

        await _dispatch_message(update, ctx, "hi", None, 5, "test")
        mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_query_chat_id_differs_from_target_sends_message(self):
        update = _callback_update(chat_id=1)
        ctx = _ctx()
        from utils.error_response import _dispatch_message

        await _dispatch_message(update, ctx, "hi", None, 99, "test")
        ctx.bot.send_message.assert_awaited_once()


# ─── send_error critical paths ──────────────────────────────────


class TestSendErrorCritical:
    @pytest.mark.asyncio
    @patch("utils.error_response._notify_critical_admins", new_callable=AsyncMock)
    async def test_critical_category_notifies_admins(self, mock_notify):
        update = _callback_update()
        ctx = _ctx()
        await send_error(update, ctx, LibRouterosError("connection refused"))
        mock_notify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_chat_id_returns_early(self):
        update = MagicMock()
        update.callback_query = None
        update.effective_message = None
        update.effective_chat = None
        ctx = _ctx()
        await send_error(update, ctx, ValueError("no target"))
        ctx.bot.send_message.assert_not_called()


# ─── _notify_critical_admins ────────────────────────────────────


class TestNotifyCriticalAdmins:
    @pytest.mark.asyncio
    @patch("config.ADMIN_IDS", [1, 2])
    @patch("utils.error_response.send_text", new_callable=AsyncMock)
    async def test_notifies_all_admins(self, mock_send_text):
        from utils.error_response import _notify_critical_admins

        update = MagicMock()
        ctx = _ctx()
        await _notify_critical_admins(update, ctx, ValueError("boom"), CATEGORY_CONNECTION, "r1", "msg")
        assert mock_send_text.await_count == 2

    @pytest.mark.asyncio
    @patch("config.ADMIN_IDS", [1])
    @patch("utils.error_response.send_text", new_callable=AsyncMock, side_effect=RuntimeError("boom"))
    @patch("utils.error_response.logger.exception")
    async def test_admin_notify_failure_logged(self, mock_exc, mock_send_text):
        from utils.error_response import _notify_critical_admins

        update = MagicMock()
        ctx = _ctx()
        await _notify_critical_admins(update, ctx, ValueError("boom"), CATEGORY_AUTH, None, "msg")
        mock_exc.assert_called()


# ─── safe_edit_plain / edit_clean benign tolerance ─────────────


class TestSafeEditsBenign:
    @pytest.mark.asyncio
    async def test_safe_edit_plain_success(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(
            return_value=Message(
                message_id=70,
                date=datetime.datetime.now(datetime.UTC),
                chat=Chat(id=1, type="private"),
            )
        )
        ctx = _ctx()
        msg = await safe_edit_plain(query, ctx, "hi", reply_markup=None)
        assert msg is not None
        query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_safe_edit_plain_benign_skip_returns_none(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Message is not modified"))
        ctx = _ctx()
        msg = await safe_edit_plain(query, ctx, "hi", reply_markup=None)
        assert msg is None

    @pytest.mark.asyncio
    async def test_safe_edit_plain_reraises_real_error(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(side_effect=BadRequest("can't parse entities"))
        ctx = _ctx()
        with pytest.raises(BadRequest):
            await safe_edit_plain(query, ctx, "hi <b>", reply_markup=None)

    @pytest.mark.asyncio
    async def test_edit_clean_benign_skip_returns_none(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Message to edit not found"))
        ctx = _ctx()
        msg = await edit_clean(query, ctx, "hi", keyboard=None)
        assert msg is None
