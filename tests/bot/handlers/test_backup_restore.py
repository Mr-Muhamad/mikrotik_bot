"""Tests for bot.handlers.backup_restore module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers.backup_restore import (
    backup_restore_start,
    backup_restore_select,
    backup_restore_confirm,
)


@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.effective_user.id = 12345
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 12345
    update.callback_query.data = "restore_backup1"
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.user_data = {}
    return context


class TestBackupRestoreStart:
    @patch("bot.handlers.backup_restore.get_selected_router", return_value=None)
    @patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock)
    async def test_no_router_ends(
        self, mock_send, mock_get_router, mock_update, mock_context
    ):
        result = await backup_restore_start(mock_update, mock_context)
        assert result is None  # Handler doesn't return explicit value

    @patch("bot.handlers.backup_restore.backup_restore")
    @patch("bot.handlers.backup_restore.get_selected_router", return_value="router1")
    @patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock)
    @patch("bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock)
    async def test_no_backups(
        self,
        mock_run,
        mock_send,
        mock_get_router,
        mock_backup_svc,
        mock_update,
        mock_context,
    ):
        mock_run.return_value = []
        result = await backup_restore_start(mock_update, mock_context)
        assert result is None  # Handler doesn't return explicit value

    @patch("bot.handlers.backup_restore.backup_restore")
    @patch("bot.handlers.backup_restore.get_selected_router", return_value="router1")
    @patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock)
    @patch("bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock)
    async def test_with_backups(
        self,
        mock_run,
        mock_send,
        mock_get_router,
        mock_backup_svc,
        mock_update,
        mock_context,
    ):
        mock_run.return_value = ["backup1", "backup2"]
        result = await backup_restore_start(mock_update, mock_context)
        assert result is None  # Should not end conversation


class TestBackupRestoreSelect:
    @patch("utils.admin_decorator.ADMIN_IDS", [12345])
    @patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock)
    async def test_select_shows_confirm(self, mock_edit, mock_update):
        mock_update.callback_query.data = "restore:0"
        context = MagicMock()
        context.user_data = {"restore_backup_list": [{"name": "backup1"}]}
        await backup_restore_select(mock_update, context)
        assert context.user_data.get("restore_backup_name") == "backup1"
        mock_edit.assert_called_once()


class TestBackupRestoreConfirm:
    @patch("bot.handlers.backup_restore.get_selected_router", return_value=None)
    async def test_no_router_ends(self, mock_get_router, mock_update, mock_context):
        mock_update.callback_query.data = "confirm_restore"
        result = await backup_restore_confirm(mock_update, mock_context)
        assert result is None  # Handler doesn't return explicit value

    @patch("bot.handlers.backup_restore.log_action")
    @patch("bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock)
    @patch("bot.handlers.backup_restore.get_selected_router", return_value="router1")
    async def test_success(
        self, mock_get_router, mock_run, mock_log, mock_update, mock_context
    ):
        mock_context.user_data["restore_backup_name"] = "backup1"
        mock_update.callback_query.data = "confirm_restore"
        mock_run.return_value = {"success": True}
        result = await backup_restore_confirm(mock_update, mock_context)
        assert result is None  # Handler doesn't return explicit value
        mock_update.callback_query.edit_message_text.assert_called()

    @patch("bot.handlers.backup_restore.log_action")
    @patch("bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock)
    @patch("bot.handlers.backup_restore.get_selected_router", return_value="router1")
    async def test_failure(
        self, mock_get_router, mock_run, mock_log, mock_update, mock_context
    ):
        mock_context.user_data["restore_backup_name"] = "backup1"
        mock_update.callback_query.data = "confirm_restore"
        mock_run.return_value = {"success": False, "message": "Connection lost"}
        result = await backup_restore_confirm(mock_update, mock_context)
        assert result is None  # Handler doesn't return explicit value
        mock_update.callback_query.edit_message_text.assert_called()
