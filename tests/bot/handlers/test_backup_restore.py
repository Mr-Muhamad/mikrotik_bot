"""Tests for bot.handlers.backup_restore module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers import backup_restore as backup_restore_module
from utils import admin_decorator

ADMIN_ID = 724730774
END = ConversationHandler.END


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _bypass_decorators():  # type: ignore[reportUnusedFunction]
    for attr in [
        "backup_restore_start",
        "backup_restore_select",
        "backup_restore_confirm",
        "userman_restore_start",
        "userman_restore_select",
        "userman_restore_execute",
    ]:
        if hasattr(backup_restore_module, attr):
            original = getattr(backup_restore_module, attr)
            while hasattr(original, "__wrapped__"):
                original = original.__wrapped__
            setattr(backup_restore_module, attr, original)


# ── helpers ────────────────────────────────────────────────────


def _cb_update(data: str = "backup_restore_start"):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.from_user = MagicMock(id=ADMIN_ID)
    update.callback_query = query
    update.message = None
    return update


def _msg_update():
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.callback_query = None
    msg = MagicMock()
    msg.text = "/backup_restore"
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _ctx(**extra):  # type: ignore[reportMissingParameterType]
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = {}
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    for k, v in extra.items():
        setattr(ctx, k, v)
    return ctx


# ── TestBackupRestoreStart ─────────────────────────────────────


class TestBackupRestoreStart:
    @pytest.mark.asyncio
    async def test_no_router_with_callback(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value=None),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.backup_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_no_router_with_message(self):
        update = _msg_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value=None),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.backup_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_exception_from_list_backups(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                side_effect=OSError("net fail"),
            ),
            patch("bot.handlers.backup_restore.send_error", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.backup_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_no_backups(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch(
                "bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock, return_value=[]
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_back_keyboard", return_value="kb"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.backup_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_with_backups(self):
        update = _cb_update()
        ctx = _ctx()
        backups = [{"name": "bk1"}, {"name": "bk2"}]
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=backups,
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_backup_restore_keyboard", return_value="kb"),
            patch("bot.handlers.backup_restore.nav_set"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.backup_restore_start(update, ctx)
        assert ctx.user_data.get("restore_backup_list") == backups
        assert result is None

    @pytest.mark.asyncio
    async def test_no_query_does_not_call_safe_answer(self):
        update = _msg_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value=None),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
            patch(
                "bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock
            ) as mock_safe,
        ):
            await backup_restore_module.backup_restore_start(update, ctx)
        mock_safe.assert_not_called()


# ── TestBackupRestoreSelect ────────────────────────────────────


class TestBackupRestoreSelect:
    @pytest.mark.asyncio
    async def test_no_query_returns(self):
        update = MagicMock()
        update.callback_query = None
        ctx = _ctx()
        result = await backup_restore_module.backup_restore_select(update, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_index(self):
        update = _cb_update("restore_backup:0")
        ctx = _ctx()
        ctx.user_data["restore_backup_list"] = [{"name": "backup_a"}, {"name": "backup_b"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.backup_restore_select(update, ctx)
        assert ctx.user_data["restore_backup_name"] == "backup_a"

    @pytest.mark.asyncio
    async def test_invalid_index(self):
        update = _cb_update("restore_backup:99")
        ctx = _ctx()
        ctx.user_data["restore_backup_list"] = [{"name": "backup_a"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.backup_restore_select(update, ctx)
        assert ctx.user_data["restore_backup_name"] == ""

    @pytest.mark.asyncio
    async def test_empty_list(self):
        update = _cb_update("restore_backup:0")
        ctx = _ctx()
        ctx.user_data["restore_backup_list"] = []
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.backup_restore_select(update, ctx)
        assert ctx.user_data["restore_backup_name"] == ""

    @pytest.mark.asyncio
    async def test_no_data_uses_default_zero(self):
        update = _cb_update("restore_backup:")
        update.callback_query.data = ""
        ctx = _ctx()
        ctx.user_data["restore_backup_list"] = [{"name": "bk"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.backup_restore_select(update, ctx)
        # Empty string is falsy → idx defaults to 0 → selects first item
        assert ctx.user_data["restore_backup_name"] == "bk"

    @pytest.mark.asyncio
    async def test_second_item(self):
        update = _cb_update("restore_backup:1")
        ctx = _ctx()
        ctx.user_data["restore_backup_list"] = [{"name": "first"}, {"name": "second"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.backup_restore_select(update, ctx)
        assert ctx.user_data["restore_backup_name"] == "second"


# ── TestBackupRestoreConfirm ───────────────────────────────────


class TestBackupRestoreConfirm:
    @pytest.mark.asyncio
    async def test_no_query_returns(self):
        update = MagicMock()
        update.callback_query = None
        ctx = _ctx()
        result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_router_key(self):
        update = _cb_update("confirm_restore")
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value=None),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
        ):
            result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result == END
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_result(self):
        update = _cb_update("confirm_restore")
        ctx = _ctx()
        ctx.user_data["restore_backup_name"] = "backup_ok"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value={"success": True},
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result == END
        texts = [call.args[0] for call in update.callback_query.edit_message_text.call_args_list]
        assert any("backup_ok" in t for t in texts)

    @pytest.mark.asyncio
    async def test_failure_result(self):
        update = _cb_update("confirm_restore")
        ctx = _ctx()
        ctx.user_data["restore_backup_name"] = "backup_bad"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value={"success": False, "message": "Timeout"},
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result == END
        texts = [call.args[0] for call in update.callback_query.edit_message_text.call_args_list]
        assert any("Timeout" in t for t in texts)

    @pytest.mark.asyncio
    async def test_exception(self):
        update = _cb_update("confirm_restore")
        ctx = _ctx()
        ctx.user_data["restore_backup_name"] = "bk_exc"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                side_effect=OSError("timeout"),
            ),
            patch("bot.handlers.backup_restore.send_error", new_callable=AsyncMock),
        ):
            result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_empty_backup_name(self):
        update = _cb_update("confirm_restore")
        ctx = _ctx()
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value={"success": True},
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.backup_restore_confirm(update, ctx)
        assert result == END


# ── TestUsermanRestoreStart ────────────────────────────────────


class TestUsermanRestoreStart:
    @pytest.mark.asyncio
    async def test_exception(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                side_effect=OSError("io"),
            ),
            patch("bot.handlers.backup_restore.send_error", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.userman_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_no_tar_files(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch(
                "bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock, return_value=[]
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_back_keyboard", return_value="kb"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.userman_restore_start(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_with_tar_files(self):
        update = _cb_update()
        ctx = _ctx()
        tar_files = [{"filename": "backup1.tar"}, {"filename": "backup2.tar"}]
        with (
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=tar_files,
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_userman_restore_keyboard", return_value="kb"),
            patch("bot.handlers.backup_restore.nav_set"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            result = await backup_restore_module.userman_restore_start(update, ctx)
        assert ctx.user_data.get("userman_restore_list") == tar_files
        assert result is None

    @pytest.mark.asyncio
    async def test_with_message_update(self):
        update = _msg_update()
        ctx = _ctx()
        tar_files = [{"filename": "a.tar"}]
        with (
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=tar_files,
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_userman_restore_keyboard", return_value="kb"),
            patch("bot.handlers.backup_restore.nav_set"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            await backup_restore_module.userman_restore_start(update, ctx)
        assert ctx.user_data.get("userman_restore_list") == tar_files

    @pytest.mark.asyncio
    async def test_no_query_skips_safe_answer(self):
        update = _msg_update()
        ctx = _ctx()
        with (
            patch(
                "bot.handlers.backup_restore.run_blocking", new_callable=AsyncMock, return_value=[]
            ),
            patch("bot.handlers.backup_restore.send_step", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_back_keyboard", return_value="kb"),
            patch(
                "bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock
            ) as mock_safe,
            patch("bot.handlers.backup_restore.cleanup_state"),
        ):
            await backup_restore_module.userman_restore_start(update, ctx)
        mock_safe.assert_not_called()


# ── TestUsermanRestoreSelect ───────────────────────────────────


class TestUsermanRestoreSelect:
    @pytest.mark.asyncio
    async def test_no_query_returns(self):
        update = MagicMock()
        update.callback_query = None
        ctx = _ctx()
        result = await backup_restore_module.userman_restore_select(update, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_index(self):
        update = _cb_update("userman_restore:0")
        ctx = _ctx()
        ctx.user_data["userman_restore_list"] = [{"filename": "a.tar"}, {"filename": "b.tar"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.userman_restore_select(update, ctx)
        assert ctx.user_data["userman_restore_tar"] == "a.tar"

    @pytest.mark.asyncio
    async def test_invalid_index(self):
        update = _cb_update("userman_restore:50")
        ctx = _ctx()
        ctx.user_data["userman_restore_list"] = [{"filename": "a.tar"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.userman_restore_select(update, ctx)
        assert ctx.user_data["userman_restore_tar"] == ""

    @pytest.mark.asyncio
    async def test_empty_list(self):
        update = _cb_update("userman_restore:0")
        ctx = _ctx()
        ctx.user_data["userman_restore_list"] = []
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.userman_restore_select(update, ctx)
        assert ctx.user_data["userman_restore_tar"] == ""

    @pytest.mark.asyncio
    async def test_no_data_uses_default_zero(self):
        update = _cb_update("userman_restore:")
        update.callback_query.data = ""
        ctx = _ctx()
        ctx.user_data["userman_restore_list"] = [{"filename": "x.tar"}]
        with (
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.edit_clean", new_callable=AsyncMock),
        ):
            await backup_restore_module.userman_restore_select(update, ctx)
        # Empty string is falsy → idx defaults to 0 → selects first item
        assert ctx.user_data["userman_restore_tar"] == "x.tar"


# ── TestFormatRestoreSummary ───────────────────────────────────


class TestFormatRestoreSummary:
    def test_all_fields_present(self):
        result = {
            "profiles_restored": 5,
            "users_restored": 20,
            "skipped": {"profiles": 1, "users": 3},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "5" in summary
        assert "20" in summary
        assert "4" in summary

    def test_only_profiles(self):
        result = {
            "profiles_restored": 3,
            "users_restored": 0,
            "skipped": {"profiles": 0, "users": 0},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "3" in summary

    def test_only_users(self):
        result = {
            "profiles_restored": 0,
            "users_restored": 10,
            "skipped": {"profiles": 0, "users": 0},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "10" in summary

    def test_only_skipped(self):
        result = {
            "profiles_restored": 0,
            "users_restored": 0,
            "skipped": {"profiles": 2, "users": 5},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "7" in summary

    def test_empty_result(self):
        result = {}
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert summary is not None and len(summary) > 0

    def test_no_skipped_field(self):
        result = {"profiles_restored": 1, "users_restored": 1}
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "1" in summary

    def test_skipped_none_values(self):
        result = {
            "profiles_restored": 0,
            "users_restored": 0,
            "skipped": {"profiles": 0, "users": 0},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert summary is not None and len(summary) > 0

    def test_only_skipped_profiles(self):
        result = {
            "profiles_restored": 0,
            "users_restored": 0,
            "skipped": {"profiles": 3, "users": 0},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "3" in summary

    def test_only_skipped_users(self):
        result = {
            "profiles_restored": 0,
            "users_restored": 0,
            "skipped": {"profiles": 0, "users": 2},
        }
        summary = backup_restore_module._format_restore_summary(result)  # type: ignore[reportPrivateUsage]
        assert "2" in summary


# ── TestUsermanRestoreExecute ──────────────────────────────────


class TestUsermanRestoreExecute:
    @pytest.mark.asyncio
    async def test_no_query_returns(self):
        update = MagicMock()
        update.callback_query = None
        ctx = _ctx()
        result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_router_key(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "backup.tar"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value=None),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_value_error_from_resolve(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "../bad.tar"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                side_effect=ValueError("bad path"),
            ),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "missing.tar"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                return_value="/tmp/missing.tar",
            ),
            patch("os.path.isfile", return_value=False),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_success_no_errors(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "good.tar"
        restore_result = {
            "success": True,
            "profiles_restored": 5,
            "users_restored": 10,
            "skipped": {"profiles": 0, "users": 0},
        }
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                return_value="/tmp/good.tar",
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=restore_result,
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_partial_with_errors(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "partial.tar"
        restore_result = {
            "success": True,
            "errors": ["profile X skipped"],
            "message": "Partial restore",
        }
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file", return_value="/tmp/p.tar"
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=restore_result,
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_failure_no_errors(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "fail.tar"
        restore_result = {"success": False, "message": "Connection refused"}
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file", return_value="/tmp/f.tar"
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=restore_result,
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END
        texts = [call.args[0] for call in update.callback_query.edit_message_text.call_args_list]
        assert any("Connection refused" in t for t in texts)

    @pytest.mark.asyncio
    async def test_exception(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "exc.tar"
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                return_value="/tmp/exc.tar",
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                side_effect=OSError("net down"),
            ),
            patch("bot.handlers.backup_restore.send_error", new_callable=AsyncMock),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_success_no_message_field(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "ok2.tar"
        restore_result = {"success": True, "profiles_restored": 0, "users_restored": 0}
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                return_value="/tmp/ok2.tar",
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=restore_result,
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END

    @pytest.mark.asyncio
    async def test_partial_restore_with_message(self):
        update = _cb_update("userman_restore_exec")
        ctx = _ctx()
        ctx.user_data["userman_restore_tar"] = "partial2.tar"
        restore_result = {
            "success": True,
            "errors": ["some error"],
            "message": "Some profiles skipped",
        }
        with (
            patch("bot.handlers.backup_restore.get_selected_router", return_value="router1"),
            patch("bot.handlers.backup_restore.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.backup_restore.get_from_user_id", return_value=ADMIN_ID),
            patch(
                "bot.handlers.backup_restore.resolve_userman_backup_file",
                return_value="/tmp/p2.tar",
            ),
            patch("os.path.isfile", return_value=True),
            patch(
                "bot.handlers.backup_restore.run_blocking",
                new_callable=AsyncMock,
                return_value=restore_result,
            ),
            patch("bot.handlers.backup_restore.log_action"),
        ):
            result = await backup_restore_module.userman_restore_execute(update, ctx)
        assert result == END
        texts = [call.args[0] for call in update.callback_query.edit_message_text.call_args_list]
        assert any("Some profiles skipped" in t for t in texts)
