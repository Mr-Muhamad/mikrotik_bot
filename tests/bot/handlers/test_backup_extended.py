"""Extended tests for backup handlers — covers schedule, download, guards.

Tests schedule_menu, schedule_enable, schedule_set, schedule_disable,
schedule_menu_from_conversation, backup_download_file, already-running guards,
and _background_backup_job with downloaded list.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.backup import (
    _BACKUP_LOCKS,  # type: ignore[reportPrivateUsage]
    _background_backup_job,  # type: ignore[reportPrivateUsage]
    backup_download_file,
    backup_full,
    backup_userman,
    schedule_disable,
    schedule_enable,
    schedule_menu,
    schedule_menu_from_conversation,
    schedule_set,
)
from bot.handlers.constants import WAITING_SCHEDULE_TIME
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774
ROUTER_KEY = "discovered_1"


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    _BACKUP_LOCKS.clear()
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    _BACKUP_LOCKS.clear()


def _make_context():
    context = make_mock_context()
    context.user_data = {"router_key": ROUTER_KEY}
    return context


# ── schedule_menu ─────────────────────────────────────────────────────
class TestScheduleMenu:
    @pytest.mark.asyncio
    async def test_schedule_menu_enabled(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="menu_schedule")
        context = _make_context()

        with patch(
            "bot.handlers.backup.backup_scheduler"
        ) as mock_sched:
            mock_sched.is_running.return_value = True
            with patch(
                "bot.handlers.backup.get_backup_schedule",
                return_value={"schedule_hour": 3, "schedule_minute": 0},
            ):
                result = await schedule_menu(update, context)

        assert result is None
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_schedule_menu_disabled(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="menu_schedule")
        context = _make_context()

        with patch(
            "bot.handlers.backup.backup_scheduler"
        ) as mock_sched:
            mock_sched.is_running.return_value = False
            result = await schedule_menu(update, context)

        assert result is None
        update.callback_query.edit_message_text.assert_awaited_once()


# ── schedule_menu_from_conversation ───────────────────────────────────
class TestScheduleMenuFromConversation:
    @pytest.mark.asyncio
    async def test_returns_end(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="menu_schedule")
        context = _make_context()

        with patch(
            "bot.handlers.backup.backup_scheduler"
        ) as mock_sched:
            mock_sched.is_running.return_value = False
            result = await schedule_menu_from_conversation(update, context)

        assert result == ConversationHandler.END


# ── schedule_enable ───────────────────────────────────────────────────
class TestScheduleEnable:
    @pytest.mark.asyncio
    async def test_returns_waiting_time(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="schedule_enable")
        context = _make_context()

        result = await schedule_enable(update, context)

        assert result == WAITING_SCHEDULE_TIME
        update.callback_query.edit_message_text.assert_awaited_once()


# ── schedule_set ──────────────────────────────────────────────────────
class TestScheduleSet:
    @pytest.mark.asyncio
    async def test_valid_time(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="03:00")
        context = _make_context()

        with patch("bot.handlers.backup.backup_scheduler"):
            with patch("bot.handlers.backup.run_blocking", new=AsyncMock()):
                result = await schedule_set(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_invalid_format(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="abc")
        context = _make_context()

        with patch("bot.handlers.backup.send_error", new=AsyncMock()):
            with patch("bot.handlers.backup.send_step", new=AsyncMock()):
                result = await schedule_set(update, context)

        assert result == WAITING_SCHEDULE_TIME

    @pytest.mark.asyncio
    async def test_out_of_range_hour(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="25:00")
        context = _make_context()

        with patch("bot.handlers.backup.send_error", new=AsyncMock()):
            with patch("bot.handlers.backup.send_step", new=AsyncMock()):
                result = await schedule_set(update, context)

        assert result == WAITING_SCHEDULE_TIME

    @pytest.mark.asyncio
    async def test_no_job_queue(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="03:00")
        context = _make_context()
        context.job_queue = None

        with patch("bot.handlers.backup.send_error", new=AsyncMock()):
            with patch("bot.handlers.backup.send_step", new=AsyncMock()):
                result = await schedule_set(update, context)

        assert result == WAITING_SCHEDULE_TIME


# ── schedule_disable ──────────────────────────────────────────────────
class TestScheduleDisable:
    @pytest.mark.asyncio
    async def test_disable(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="schedule_disable")
        context = _make_context()

        with patch("bot.handlers.backup.backup_scheduler") as mock_sched:
            with patch("bot.handlers.backup.run_blocking", new=AsyncMock()):
                result = await schedule_disable(update, context)

        assert result is None
        mock_sched.stop.assert_called_once_with(context.job_queue)

    @pytest.mark.asyncio
    async def test_disable_no_job_queue(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="schedule_disable")
        context = _make_context()
        context.job_queue = None

        result = await schedule_disable(update, context)

        assert result is None


# ── backup_full: already running guard ────────────────────────────────
class TestBackupFullAlreadyRunning:
    @pytest.mark.asyncio
    async def test_already_running(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_full")
        context = _make_context()

        _BACKUP_LOCKS[ROUTER_KEY] = True

        result = await backup_full(update, context)

        assert result is None
        update.callback_query.edit_message_text.assert_awaited_once()
        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "قيد التنفيذ" in edit_text or "running" in edit_text.lower() or "جاري" in edit_text


# ── backup_userman: already running guard ─────────────────────────────
class TestBackupUsermanAlreadyRunning:
    @pytest.mark.asyncio
    async def test_already_running(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_userman")
        context = _make_context()

        _BACKUP_LOCKS[ROUTER_KEY] = True

        result = await backup_userman(update, context)

        assert result is None
        update.callback_query.edit_message_text.assert_awaited_once()


# ── _background_backup_job ────────────────────────────────────────────
class TestBackgroundBackupJob:
    def _make_job_context(self, b_type="full"):  # type: ignore[reportMissingParameterType]
        context = MagicMock()
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        job = MagicMock()
        job.data = {
            "router_key": ROUTER_KEY,
            "chat_id": 12345,
            "user_id": ADMIN_ID,
            "type": b_type,
        }
        context.job = job
        return context

    @pytest.mark.asyncio
    async def test_full_backup_success_with_downloaded(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": True, "message": "ok", "downloaded": ["file1.backup", "file2.backup"]},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited()
        text = ctx.bot.send_message.call_args[1]["text"]
        assert "2" in text

    @pytest.mark.asyncio
    async def test_full_backup_success_no_downloaded(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": True, "message": "ok"},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_full_backup_failure(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": False, "message": "fail"},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_userman_backup_success_no_filename(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("userman")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": True, "message": "ok"},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_userman_backup_failure(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("userman")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": False, "message": "fail"},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_sends_error(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = OSError("crash")
            await _background_backup_job(ctx)

        ctx.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_released_on_success(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")
        _BACKUP_LOCKS[ROUTER_KEY] = True

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = [
                {"success": True, "message": "ok"},
                None,
                None,
            ]
            await _background_backup_job(ctx)

        assert ROUTER_KEY not in _BACKUP_LOCKS

    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        ctx = self._make_job_context("full")
        _BACKUP_LOCKS[ROUTER_KEY] = True

        with patch("bot.handlers.backup.run_blocking", new_callable=AsyncMock) as mock_rb:
            mock_rb.side_effect = OSError("crash")
            await _background_backup_job(ctx)

        assert ROUTER_KEY not in _BACKUP_LOCKS


# ── backup_download_file ──────────────────────────────────────────────
class TestBackupDownloadFile:
    @pytest.mark.asyncio
    async def test_invalid_format(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:")
        context = _make_context()

        result = await backup_download_file(update, context)

        assert result is None
        assert update.callback_query.answer.await_count >= 1

    @pytest.mark.asyncio
    async def test_index_out_of_range(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:99")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["file1.backup"]

        result = await backup_download_file(update, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_type(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:unknown:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["file1.backup"]

        result = await backup_download_file(update, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["nonexistent.backup"]

        with patch(
            "bot.handlers.backup.resolve_local_backup_file",
            return_value="/tmp/nonexistent.backup",
        ):
            result = await backup_download_file(update, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_file_too_large(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["big.backup"]

        with tempfile.NamedTemporaryFile(suffix=".backup", delete=False) as f:
            f.write(b"x" * (50 * 1024 * 1024))
            fpath = f.name

        try:
            with patch(
                "bot.handlers.backup.resolve_local_backup_file",
                return_value=fpath,
            ):
                result = await backup_download_file(update, context)

            assert result is None
        finally:
            os.unlink(fpath)

    @pytest.mark.asyncio
    async def test_unsafe_path_rejected(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["../../../etc/passwd"]

        with patch(
            "bot.handlers.backup.resolve_local_backup_file",
            side_effect=ValueError("unsafe path"),
        ):
            result = await backup_download_file(update, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_success(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["test.backup"]

        with tempfile.NamedTemporaryFile(suffix=".backup", delete=False) as f:
            f.write(b"backup data")
            fpath = f.name

        try:
            with patch(
                "bot.handlers.backup.resolve_local_backup_file",
                return_value=fpath,
            ):
                with patch(
                    "bot.handlers.backup.get_query_message",
                    return_value=update.callback_query.message,
                ):
                    result = await backup_download_file(update, context)

            assert result is None
            context.bot.send_document.assert_awaited_once()
        finally:
            os.unlink(fpath)

    @pytest.mark.asyncio
    async def test_no_query_message(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(callback_data="backup_dl:full:0")
        context = _make_context()
        context.user_data["backup_downloaded_list"] = ["test.backup"]

        with tempfile.NamedTemporaryFile(suffix=".backup", delete=False) as f:
            f.write(b"backup data")
            fpath = f.name

        try:
            with patch(
                "bot.handlers.backup.resolve_local_backup_file",
                return_value=fpath,
            ):
                with patch("bot.handlers.backup.get_query_message", return_value=None):
                    result = await backup_download_file(update, context)

            assert result is None
        finally:
            os.unlink(fpath)
