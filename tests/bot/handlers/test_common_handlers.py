"""Tests for the common handlers (start, help, cancel, clean, main_menu)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.common import (
    cancel,
    clean_chat,
    help_command,
    main_menu,
    select_router_callback,
    start,
)
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.set_my_commands = AsyncMock()
    context.bot.delete_message = AsyncMock()
    return context


class TestStart:
    @pytest.mark.asyncio
    async def test_start_clears_router_and_state(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, "discovered_1")
        update = make_mock_update(text="/start")
        context = _make_context()
        context.user_data["add_username"] = "data"

        with patch("bot.handlers.common.mikrotik_api") as mock_api:
            mock_api.check_connection_health.return_value = (True, "OK")
            result = await start(update, context)

        assert result == ConversationHandler.END
        assert "add_username" not in context.user_data

    @pytest.mark.asyncio
    async def test_start_sends_welcome(self, mock_mikrotik_api):
        update = make_mock_update(text="/start")
        context = _make_context()

        await start(update, context)
        # start sends a temp status message then the main menu (at least one call)
        assert context.bot.send_message.call_count >= 1


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_help_sends_message(self, mock_mikrotik_api):
        update = make_mock_update(text="/help")
        context = _make_context()

        await help_command(update, context)
        context.bot.send_message.assert_called_once()


class TestMainMenu:
    @pytest.mark.asyncio
    async def test_main_menu_with_router(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, "discovered_1")
        update = make_mock_update(callback_data="main_menu")
        context = _make_context()

        with patch("bot.handlers.common.mikrotik_api"):
            result = await main_menu(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_main_menu_without_router(self, mock_mikrotik_api):
        from bot.router_selector import clear_router

        clear_router(ADMIN_ID)
        update = make_mock_update(callback_data="main_menu")
        context = _make_context()

        result = await main_menu(update, context)
        assert result == ConversationHandler.END


class TestSelectRouterCallback:
    @pytest.mark.asyncio
    async def test_select_router(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="select_router")
        context = _make_context()

        result = await select_router_callback(update, context)
        assert result == ConversationHandler.END
        assert update.callback_query.edit_message_text.called


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_with_callback(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="cancel_edit")
        context = _make_context()

        result = await cancel(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_with_message(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, "discovered_1")
        update = make_mock_update(text="/cancel")
        context = _make_context()
        context.user_data["last_msg"] = 12345

        with patch("bot.handlers.common.mikrotik_api"):
            await cancel(update, context)
        assert context.bot.send_message.called or update.message.delete.called


class TestCleanChat:
    @pytest.mark.asyncio
    async def test_clean_chat_sends_confirmation(self, mock_mikrotik_api):
        update = make_mock_update(text="/clean")
        context = _make_context()
        sent_msg = MagicMock()
        sent_msg.message_id = 555
        context.bot.send_message = AsyncMock(return_value=sent_msg)

        with patch("bot.handlers.common.clean_chat_messages", new=AsyncMock()), patch(
            "bot.handlers.common.schedule_delete", new=AsyncMock()
        ) as mock_sched:
            await clean_chat(update, context)
        mock_sched.assert_called_once()
