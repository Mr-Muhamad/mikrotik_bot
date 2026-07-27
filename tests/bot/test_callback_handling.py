"""Unit tests for callback query handling, stale callback prevention, and zero-latency answers."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath("."))

from bot.registration_parts.conversation import _unhandled_callback_handler
from utils.callback_utils import is_latest_message
from utils.handler_registry import _registry


def test_pdf_group_text_and_go_back_registered_standalone():
    """Verify pdf_group_text and go_back are registered in standalone handlers."""

    registered_funcs = [
        item["func"].__name__
        for item in _registry["standalone"]
        if item["cls"].__name__ == "CallbackQueryHandler"
    ]
    assert "pdf_group_text" in registered_funcs
    assert "go_back" in registered_funcs


@pytest.mark.asyncio
async def test_unhandled_callback_handler_zero_latency_and_graceful_edit():
    """Verify _unhandled_callback_handler answers instantly and edits stale message without alert."""
    query = AsyncMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await _unhandled_callback_handler(update, context)

    # 1. Immediate safe answer (no alert popup)
    query.answer.assert_called_once_with(text=None, show_alert=False)

    # 2. Graceful message edit with main menu keyboard
    query.edit_message_text.assert_called_once()
    args, kwargs = query.edit_message_text.call_args
    assert "⚠️ هذه القائمة قديمة أو منتهية الصلاحية." in args[0]
    assert kwargs.get("reply_markup") is not None


def test_is_latest_message_check():
    """Verify is_latest_message helper function correctly identifies active vs stale messages."""
    query = MagicMock(spec=CallbackQuery)
    msg = MagicMock(spec=Message)
    msg.message_id = 100
    query.message = msg

    # No last_msg tracked -> returns True
    assert is_latest_message(query, {}) is True

    # Matching last_msg -> returns True
    assert is_latest_message(query, {"last_msg": 100}) is True

    # Stale message -> returns False
    assert is_latest_message(query, {"last_msg": 105}) is False
