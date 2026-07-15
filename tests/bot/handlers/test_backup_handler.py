"""Tests for bot.handlers.backup."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import ConversationHandler

from bot.handlers import backup as backup_module
from bot.handlers.constants import WAITING_SCHEDULE_TIME
from utils import admin_decorator


ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


@pytest.fixture(autouse=True)
def _bypass_decorators():
    """Bypass @admin_only/@require_router by replacing decorated functions with their unwrapped versions."""
    for attr in ["backup_full", "backup_userman", "schedule_menu",
                 "schedule_menu_from_conversation", "schedule_enable",
                 "schedule_set", "schedule_disable"]:
        if hasattr(backup_module, attr):
            original = getattr(backup_module, attr)
            while hasattr(original, "__wrapped__"):
                original = original.__wrapped__
            setattr(backup_module, attr, original)


def _query_update():
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock(id=ADMIN_ID)
    update.callback_query = query
    return update


def _text_update(text):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.message = MagicMock()
    update.message.text = text
    return update


class TestBackupFull:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": True, "message": "Backup complete", "local_path": "/tmp/backup.backup"}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \
             patch("bot.handlers.backup.edit_clean", new=AsyncMock()), \
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Disk full", "local_path": ""}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "❌" in text
        assert "Disk full" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(side_effect=Exception("net down"))):
            await backup_module.backup_full(update, ctx)
        # Two calls: progress message + error response
        assert update.callback_query.edit_message_text.call_count == 2
        last_call_kwargs = update.callback_query.edit_message_text.call_args_list[-1].kwargs
        text = last_call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "❌" in text


class TestBackupUserman:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {
            "success": True, "message": "UserMan backup complete",
            "local_path": "/tmp/um.umb", "users_count": 50, "profiles_count": 5
        }

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)
        text = update.callback_query.edit_message_text.call_args.kwargs.get("text", "")
        assert "50" in text
        assert "5" in text

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Auth failed", "local_path": ""}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "❌" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(side_effect=Exception("timeout"))):
            await backup_module.backup_userman(update, ctx)
        # Two calls: progress message + error response
        assert update.callback_query.edit_message_text.call_count == 2
        last_call_kwargs = update.callback_query.edit_message_text.call_args_list[-1].kwargs
        text = last_call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "❌" in text


class TestScheduleMenu:
    @pytest.mark.asyncio
    async def test_disabled(self):
        ctx = MagicMock()
        ctx.job_queue = MagicMock()
        update = _query_update()

        with patch("bot.handlers.backup.backup_scheduler.is_running", return_value=False), \
             patch("bot.handlers.backup.get_backup_schedule", return_value={"schedule_hour": 3, "schedule_minute": 0}):
            await backup_module.schedule_menu(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "❌" in text or "معطل" in text

    @pytest.mark.asyncio
    async def test_enabled(self):
        ctx = MagicMock()
        ctx.job_queue = MagicMock()
        update = _query_update()

        with patch("bot.handlers.backup.backup_scheduler.is_running", return_value=True), \
             patch("bot.handlers.backup.get_backup_schedule", return_value={"schedule_hour": 3, "schedule_minute": 30}):
            await backup_module.schedule_menu(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "3:30" in text


class TestScheduleMenuFromConversation:
    @pytest.mark.asyncio
    async def test_returns_end(self):
        ctx = MagicMock()
        ctx.user_data = {}
        update = _query_update()

        with patch("bot.handlers.backup.backup_scheduler.is_running", return_value=False), \
             patch("bot.handlers.backup.get_backup_schedule", return_value={"schedule_hour": 0, "schedule_minute": 0}):
            result = await backup_module.schedule_menu_from_conversation(update, ctx)
        assert result == ConversationHandler.END


class TestScheduleEnable:
    @pytest.mark.asyncio
    async def test_enables(self):
        ctx = MagicMock()
        ctx.user_data = {}
        update = _query_update()
        with patch("bot.router_selector.get_user_session", return_value={}), \
             patch("bot.router_selector.save_user_session"):
            result = await backup_module.schedule_enable(update, ctx)
        assert result == WAITING_SCHEDULE_TIME


class TestScheduleSet:
    @pytest.mark.asyncio
    async def test_valid_time(self):
        ctx = MagicMock()
        ctx.user_data = {}
        ctx.job_queue = MagicMock()
        update = _text_update("03:30")

        with patch("bot.router_selector.get_user_session", return_value={}), \
             patch("bot.router_selector.save_user_session"), \
             patch("bot.handlers.backup.backup_scheduler.start_daily") as mock_start, \
             patch("bot.handlers.backup.reply_final", new=AsyncMock()), \
             patch("bot.handlers.backup.log_action"):
            result = await backup_module.schedule_set(update, ctx)
        assert result == ConversationHandler.END
        mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_format_reprompts(self):
        ctx = MagicMock()
        ctx.user_data = {}
        update = _text_update("abc")

        with patch("bot.router_selector.get_user_session", return_value={}), \
             patch("bot.router_selector.save_user_session"), \
             patch("bot.handlers.backup.send_step", new=AsyncMock()) as mock_step:
            result = await backup_module.schedule_set(update, ctx)
        assert result == WAITING_SCHEDULE_TIME
        mock_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_hour_out_of_range(self):
        ctx = MagicMock()
        ctx.user_data = {}
        update = _text_update("25:00")

        with patch("bot.router_selector.get_user_session", return_value={}), \
             patch("bot.router_selector.save_user_session"), \
             patch("bot.handlers.backup.send_step", new=AsyncMock()):
            result = await backup_module.schedule_set(update, ctx)
        assert result == WAITING_SCHEDULE_TIME

    @pytest.mark.asyncio
    async def test_minute_out_of_range(self):
        ctx = MagicMock()
        ctx.user_data = {}
        update = _text_update("10:70")

        with patch("bot.router_selector.get_user_session", return_value={}), \
             patch("bot.router_selector.save_user_session"), \
             patch("bot.handlers.backup.send_step", new=AsyncMock()):
            result = await backup_module.schedule_set(update, ctx)
        assert result == WAITING_SCHEDULE_TIME


class TestScheduleDisable:
    @pytest.mark.asyncio
    async def test_disables(self):
        ctx = MagicMock()
        ctx.user_data = {}
        ctx.job_queue = MagicMock()
        update = _query_update()

        with patch("bot.handlers.backup.backup_scheduler.stop") as mock_stop, \
             patch("bot.handlers.backup.log_action"):
            await backup_module.schedule_disable(update, ctx)
        mock_stop.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
