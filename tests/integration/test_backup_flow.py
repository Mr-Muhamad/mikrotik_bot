"""Integration-style tests for the backup flow.

Tests the end-to-end backup flow through the backup_service using
the in-memory MikrotikAPIMock.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.backup_service import backup_service

ROUTER_KEY = "discovered_1"


class TestBackupService:
    def test_full_backup_creates_local_dir(self, mock_mikrotik_api, temp_backup_dir):
        with patch("core.backup_service.BACKUP_DIR", temp_backup_dir):
            result = backup_service.full_backup(ROUTER_KEY)

        assert result["success"] is True
        assert "تم الباكوب الكامل" in result["message"]
        assert os.path.isdir(result["local_path"])
        backup_commands = [
            c
            for c in mock_mikrotik_api.commands_executed
            if c[1] in ("system/backup/save", "export")
        ]
        assert len(backup_commands) >= 2

    def test_full_backup_failure_returns_dict(self, mock_mikrotik_api, temp_backup_dir):
        with patch("core.backup_service.BACKUP_DIR", temp_backup_dir), patch.object(
            mock_mikrotik_api, "execute_long", side_effect=Exception("router offline")
        ):
            result = backup_service.full_backup(ROUTER_KEY)

        assert result["success"] is False
        assert "فشل" in result["message"]
        assert "router offline" in result["message"]

    def test_userman_backup_creates_local_dir(self, mock_mikrotik_api, temp_backup_dir):
        with patch("core.backup_service.BACKUP_DIR", temp_backup_dir):
            result = backup_service.userman_backup(ROUTER_KEY)

        assert result["success"] is True
        assert "تم" in result["message"]

    def test_userman_backup_failure_returns_dict(
        self, mock_mikrotik_api, temp_backup_dir
    ):
        with patch("core.backup_service.BACKUP_DIR", temp_backup_dir), patch.object(
            mock_mikrotik_api, "execute", side_effect=Exception("timeout")
        ):
            result = backup_service.userman_backup(ROUTER_KEY)

        assert result["success"] is False
        assert "فشل" in result["message"]


class TestBackupHandlers:
    """End-to-end tests for the backup Telegram handlers."""

    def _make_context(self):
        context = MagicMock()
        context.user_data = {}
        context.bot_data = {}
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_backup_full_handler_success(
        self, mock_mikrotik_api, temp_backup_dir
    ):
        from bot.handlers.backup import backup_full
        from database.models import save_user_session
        from tests.fixtures.telegram_mocks import make_mock_update
        from utils import admin_decorator

        admin_decorator._rate_limit_data.clear()
        save_user_session(724730774, ROUTER_KEY)
        try:
            update = make_mock_update(callback_data="backup_full")
            context = self._make_context()
            context.user_data["router_key"] = ROUTER_KEY
            mock_mikrotik_api.commands_executed.clear()

            with patch("core.backup_service.BACKUP_DIR", temp_backup_dir), patch(
                "bot.handlers.backup.log_action"
            ):
                await backup_full(update, context)

                # Extract and run job
                job_func = context.job_queue.run_once.call_args[0][0]
                job_mock = MagicMock()
                job_mock.data = context.job_queue.run_once.call_args.kwargs.get("data")
                job_ctx = MagicMock()
                job_ctx.job = job_mock
                job_ctx.bot.send_message = AsyncMock()
                await job_func(job_ctx)

            assert any(
                c[1] in ("system/backup/save", "export")
                for c in mock_mikrotik_api.commands_executed
            )
        finally:
            admin_decorator._rate_limit_data.clear()

    @pytest.mark.asyncio
    async def test_backup_userman_handler_success(
        self, mock_mikrotik_api, temp_backup_dir
    ):
        from bot.handlers.backup import backup_userman
        from database.models import save_user_session
        from tests.fixtures.telegram_mocks import make_mock_update
        from utils import admin_decorator

        admin_decorator._rate_limit_data.clear()
        save_user_session(724730774, ROUTER_KEY)
        try:
            update = make_mock_update(callback_data="backup_userman")
            context = self._make_context()
            context.user_data["router_key"] = ROUTER_KEY

            with patch("core.backup_service.BACKUP_DIR", temp_backup_dir), patch(
                "bot.handlers.backup.log_action"
            ):
                await backup_userman(update, context)

            assert update.callback_query.edit_message_text.called
        finally:
            admin_decorator._rate_limit_data.clear()


@pytest.fixture
def temp_backup_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_full_backup_cleanup_uses_file_prefix(mock_mikrotik_api, temp_backup_dir):
    from unittest.mock import patch as _patch

    with _patch("core.backup_service.BACKUP_DIR", temp_backup_dir), _patch(
        "core.backup.system.cleanup_old_backups"
    ) as mock_cleanup:
        result = backup_service.full_backup(ROUTER_KEY)

    assert result["success"] is True
    assert mock_cleanup.called
    # cleanup must key on the sanitized router-name prefix, not the router_key
    prefix_arg = mock_cleanup.call_args.args[1]
    assert prefix_arg == "TestRouter"
    assert prefix_arg != ROUTER_KEY
