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
    for attr in [
        "backup_full",
        "backup_userman",
        "schedule_menu",
        "schedule_menu_from_conversation",
        "schedule_enable",
        "schedule_set",
        "schedule_disable",
    ]:
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
        result = {
            "success": True,
            "message": "Backup complete",
            "local_path": "/tmp/backup.backup",
        }

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ), patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)

        ctx.job_queue.run_once.assert_called_once()

        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ):
            await job_func(job_ctx)

        job_ctx.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Disk full", "local_path": ""}

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ), patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)

        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ):
            await job_func(job_ctx)

        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text
        assert "Disk full" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        await backup_module.backup_full(update, ctx)
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking",
            new=AsyncMock(side_effect=Exception("net down")),
        ):
            await job_func(job_ctx)

        job_ctx.bot.send_message.assert_called_once()
        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text


class TestBackupUserman:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {
            "success": True,
            "message": "UserMan backup complete",
            "local_path": "/tmp/um.umb",
            "users_count": 50,
            "profiles_count": 5,
        }

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ), patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)

        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ):
            await job_func(job_ctx)

        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "User Manager" in text
        assert "✅" in text

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Auth failed", "local_path": ""}

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ), patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)

        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)
        ):
            await job_func(job_ctx)

        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        await backup_module.backup_userman(update, ctx)

        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()

        with patch(
            "bot.handlers.backup.run_blocking",
            new=AsyncMock(side_effect=Exception("timeout")),
        ):
            await job_func(job_ctx)

        job_ctx.bot.send_message.assert_called_once()
