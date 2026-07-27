"""Tests for bot/handlers/timeout.py - session timeout configuration."""

import sqlite3
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.timeout"


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(f"{P}.set_session_timeout"))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestCmdTimeout:
    @pytest.mark.asyncio
    async def test_with_message(self):
        from bot.handlers.timeout import cmd_timeout

        update = make_mock_update()
        ctx = make_mock_context()
        await cmd_timeout(update, ctx)
        update.message.reply_html.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_callback_query(self):
        from bot.handlers.timeout import cmd_timeout

        update = make_mock_update(callback_data="open_timeout")
        ctx = make_mock_context()
        await cmd_timeout(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()


class TestHandleTimeoutSelection:
    @pytest.mark.asyncio
    async def test_save_timeout_15_minutes(self):
        import bot.handlers.timeout as mod

        update = make_mock_update(callback_data="set_timeout:15")
        ctx = make_mock_context()
        await mod.handle_timeout_selection(update, ctx)
        mod.set_session_timeout.assert_called_once_with(724730774, 15)
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_timeout_no_limit(self):
        import bot.handlers.timeout as mod

        update = make_mock_update(callback_data="set_timeout:0")
        ctx = make_mock_context()
        await mod.handle_timeout_selection(update, ctx)
        mod.set_session_timeout.assert_called_once_with(724730774, 0)

    @pytest.mark.asyncio
    async def test_cancel_timeout(self):
        from bot.handlers.timeout import handle_timeout_selection

        update = make_mock_update(callback_data="cancel_timeout")
        ctx = make_mock_context()
        await handle_timeout_selection(update, ctx)
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_handling_on_save_failure(self):
        from bot.handlers.timeout import handle_timeout_selection

        with patch(f"{P}.set_session_timeout", side_effect=sqlite3.Error("db error")):
            update = make_mock_update(callback_data="set_timeout:5")
            ctx = make_mock_context()
            await handle_timeout_selection(update, ctx)
            update.callback_query.edit_message_text.assert_awaited_once()
