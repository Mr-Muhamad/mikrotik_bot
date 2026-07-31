"""Tests for bot/handlers/commands_basic.py — /start, /help, /cancel, /clean,
/sync, /metrics, select_router, error_handler, and reprompt handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import telegram.error
from telegram.ext import ConversationHandler

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.commands_basic"


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(f"{P}.send_and_track", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.schedule_delete", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.delete_now", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.clean_chat_messages", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_selected_router", return_value=None))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.clear_action"))
    stack.enter_context(patch(f"{P}.clear_router"))
    stack.enter_context(patch(f"{P}.set_current_action"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestStart:
    @pytest.mark.asyncio
    @patch(f"{P}.send_and_track", new_callable=AsyncMock)
    async def test_no_router_shows_welcome(self, mock_send):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import start

        result = await start(update, context)
        assert result == ConversationHandler.END
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value="discovered_1")
    @patch(f"{P}.send_and_track", new_callable=AsyncMock)
    @patch("bot.handlers.commands_basic._get_router_part", new_callable=AsyncMock)
    @patch("bot.handlers.commands_basic._get_router_system_part", new_callable=AsyncMock)
    @patch("bot.router_selector.fast_reachability_check", new_callable=AsyncMock)
    async def test_with_router_reachable(self, mock_fast, mock_sys, mock_rp, mock_send, _rp):
        mock_fast.return_value = True
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import start

        result = await start(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value="discovered_1")
    @patch(f"{P}.send_and_track", new_callable=AsyncMock)
    @patch("bot.router_selector.fast_reachability_check", new_callable=AsyncMock)
    async def test_with_router_offline(self, mock_fast, mock_send, _rp):
        mock_fast.return_value = False
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import start

        result = await start(update, context)
        assert result == ConversationHandler.END


class TestSelectRouterCallback:
    @pytest.mark.asyncio
    async def test_clears_and_shows_welcome(self):
        update = make_mock_update(callback_data="select_router")
        context = make_mock_context()
        from bot.handlers.commands_basic import select_router_callback

        result = await select_router_callback(update, context)
        assert result == ConversationHandler.END


class TestCancel:
    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value="discovered_1")
    @patch("bot.handlers.commands_basic._get_router_part", new_callable=AsyncMock)
    @patch("bot.handlers.commands_basic._get_router_system_part", new_callable=AsyncMock)
    async def test_callback_with_router(self, _rs, _rp, _rr):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.commands_basic import cancel

        result = await cancel(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value=None)
    async def test_callback_no_router(self, _rr):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.commands_basic import cancel

        result = await cancel(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value="discovered_1")
    @patch("bot.handlers.commands_basic._get_router_part", new_callable=AsyncMock)
    @patch("bot.handlers.commands_basic._get_router_system_part", new_callable=AsyncMock)
    async def test_message_with_router(self, _rs, _rp, _rr):
        update = make_mock_update()
        context = make_mock_context()
        context.user_data["last_msg"] = 42
        from bot.handlers.commands_basic import cancel

        result = await cancel(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}.get_selected_router", return_value=None)
    async def test_message_no_router(self, _rr):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import cancel

        result = await cancel(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}._resolve_nav_target")
    @patch(f"{P}.get_selected_router", return_value=None)
    async def test_with_nav_target(self, _rr, mock_resolve):
        mock_handler = AsyncMock()
        mock_resolve.return_value = mock_handler
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        context.user_data["nav_back"] = "menu_hotspot"
        from bot.handlers.commands_basic import cancel

        result = await cancel(update, context)
        assert result == ConversationHandler.END
        mock_handler.assert_called_once_with(update, context)


class TestErrorHandler:
    @pytest.mark.asyncio
    async def test_non_critical_error_ignored(self):
        update = make_mock_update()
        context = make_mock_context()
        context.error = Exception("Message is not modified")
        from bot.handlers.commands_basic import error_handler

        await error_handler(update, context)
        context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{P}.send_and_track", new_callable=AsyncMock)
    async def test_critical_error_sends_message(self, mock_send):
        update = make_mock_update()
        context = make_mock_context()
        context.error = Exception("something broke")
        from bot.handlers.commands_basic import error_handler

        await error_handler(update, context)
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_without_update_notifies_admin(self):
        context = make_mock_context()
        context.error = Exception("bg failure")
        with patch("config.ADMIN_IDS", [724730774]):
            with patch("utils.error_response.sanitize_error_text", return_value="clean text"):
                from bot.handlers.commands_basic import error_handler

                await error_handler(None, context)
        context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_without_update_send_fails(self):
        context = make_mock_context()
        context.error = Exception("bg fail")
        context.bot.send_message.side_effect = telegram.error.TelegramError("tg down")
        with patch("config.ADMIN_IDS", [724730774]):
            with patch("utils.error_response.sanitize_error_text", return_value="clean text"):
                from bot.handlers.commands_basic import error_handler

                await error_handler(None, context)

    @pytest.mark.asyncio
    async def test_no_error_attribute(self):
        update = make_mock_update()
        context = make_mock_context()
        context.error = None
        from bot.handlers.commands_basic import error_handler

        await error_handler(update, context)

    @pytest.mark.asyncio
    async def test_httpx_read_error_ignored(self):
        update = make_mock_update()
        context = make_mock_context()
        context.error = Exception("httpx.ReadError")
        from bot.handlers.commands_basic import error_handler

        await error_handler(update, context)
        context.bot.send_message.assert_not_called()


class TestHelpCommand:
    @pytest.mark.asyncio
    @patch(f"{P}.send_and_track", new_callable=AsyncMock)
    async def test_sends_help(self, mock_send):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import help_command

        await help_command(update, context)
        mock_send.assert_called_once()


class TestCleanChat:
    @pytest.mark.asyncio
    async def test_cleans_and_sends_done(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import clean_chat

        await clean_chat(update, context)
        context.bot.send_message.assert_called_once()


class TestSyncCommands:
    @pytest.mark.asyncio
    @patch(f"{P}.set_bot_commands", new_callable=AsyncMock)
    async def test_syncs_commands(self, mock_set):
        update = make_mock_update()
        context = make_mock_context()
        context.application = MagicMock()
        from bot.handlers.commands_basic import sync_commands

        await sync_commands(update, context)
        context.bot.send_message.assert_called_once()


class TestMetricsCommand:
    @pytest.mark.asyncio
    @patch(f"{P}.mikrotik_api")
    async def test_sends_metrics(self, mock_api):
        mock_api.get_metrics.return_value = {
            "total_attempts": 100,
            "successful": 95,
            "failed": 5,
            "active_connections": 2,
            "idle_connections": 0,
            "cache_hits": 10,
        }
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import metrics_command

        await metrics_command(update, context)
        context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{P}.mikrotik_api")
    async def test_metrics_psutil_import_error(self, mock_api):
        mock_api.get_metrics.return_value = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
        }
        update = make_mock_update()
        context = make_mock_context()
        with patch.dict("sys.modules", {"psutil": None}):
            from bot.handlers.commands_basic import metrics_command

            await metrics_command(update, context)
        context.bot.send_message.assert_called_once()


class TestReprompts:
    @pytest.mark.asyncio
    async def test_reprompt_select_user(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import reprompt_select_user

        result = await reprompt_select_user(update, context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_reprompt_card_type(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import reprompt_card_type_text

        result = await reprompt_card_type_text(update, context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_reprompt_card_profile(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.commands_basic import reprompt_card_profile_text

        result = await reprompt_card_profile_text(update, context)
        assert result is not None
