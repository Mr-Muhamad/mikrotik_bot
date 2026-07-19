"""Tests for utils.error_response benign-error handling and chat_cleaner safe edits."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import BadRequest

from utils.chat_cleaner import edit_clean, safe_edit_plain
from utils.error_response import is_benign_telegram_error, send_error


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
        query.edit_message_text = AsyncMock(return_value=MagicMock(message_id=61))
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
        assert (
            is_benign_telegram_error(BadRequest("message is exactly the same content"))
            is True
        )

    def test_other_badrequest_not_benign(self):
        assert is_benign_telegram_error(BadRequest("can't parse entities")) is False

    def test_non_badrequest_not_benign(self):
        assert is_benign_telegram_error(ValueError("boom")) is False


# ─── send_error benign handling ─────────────────────────────────


class TestSendErrorBenign:
    @pytest.mark.asyncio
    @patch("utils.error_response.logger.debug")
    async def test_benign_logged_debug_and_no_user_message(self, mock_debug):
        update = _callback_update()
        ctx = _ctx()
        error = BadRequest("Message is not modified")
        await send_error(update, ctx, error)
        # No user-facing message should be dispatched
        update.callback_query.edit_message_text.assert_not_called()
        ctx.bot.send_message.assert_not_called()
        # Verify it was logged as debug
        assert mock_debug.call_count == 1
        log_msg = mock_debug.call_args[0][0]
        assert "Benign" in log_msg

    @pytest.mark.asyncio
    async def test_real_error_still_dispatches(self):
        update = _callback_update()
        ctx = _ctx()
        error = ValueError("real failure")
        await send_error(update, ctx, error)
        # Real errors still reach the user via edit_message_text
        update.callback_query.edit_message_text.assert_awaited_once()


# ─── safe_edit_plain / edit_clean benign tolerance ─────────────


class TestSafeEditsBenign:
    @pytest.mark.asyncio
    async def test_safe_edit_plain_success(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(return_value=MagicMock(message_id=70))
        ctx = _ctx()
        msg = await safe_edit_plain(query, ctx, "hi", reply_markup=None)
        assert msg is not None
        query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_safe_edit_plain_benign_skip_returns_none(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(
            side_effect=BadRequest("Message is not modified")
        )
        ctx = _ctx()
        msg = await safe_edit_plain(query, ctx, "hi", reply_markup=None)
        assert msg is None

    @pytest.mark.asyncio
    async def test_safe_edit_plain_reraises_real_error(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(
            side_effect=BadRequest("can't parse entities")
        )
        ctx = _ctx()
        with pytest.raises(BadRequest):
            await safe_edit_plain(query, ctx, "hi <b>", reply_markup=None)

    @pytest.mark.asyncio
    async def test_edit_clean_benign_skip_returns_none(self):
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock(
            side_effect=BadRequest("Message to edit not found")
        )
        ctx = _ctx()
        msg = await edit_clean(query, ctx, "hi", keyboard=None)
        assert msg is None
