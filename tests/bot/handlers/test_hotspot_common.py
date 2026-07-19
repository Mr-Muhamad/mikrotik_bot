"""Tests for bot.handlers.hotspot_common."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import ConversationHandler

from bot.handlers.hotspot_common import search_users_for_action, execute_add_user
from bot.handlers.session_models import get_hotspot_add_session
from bot.handlers.constants import (
    WAITING_DELETE_ID,
    WAITING_DELETE_SELECT,
    WAITING_EDIT_FIELD,
    WAITING_EDIT_VALUE,
    WAITING_INPUT,
)

ADMIN_ID = 724730774


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


def _update():
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.message = MagicMock()
    update.message.text = "ali"
    return update


class TestSearchUsersForAction:
    @pytest.mark.asyncio
    async def test_no_router_ends(self):
        with patch(
            "bot.handlers.hotspot_common.get_selected_router", return_value=None
        ), patch(
            "bot.handlers.hotspot_common.reply_final", new=AsyncMock()
        ) as mock_reply:
            result = await search_users_for_action(_update(), _ctx(), "delete")
        assert result == ConversationHandler.END
        mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_exception_ends(self):
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(side_effect=Exception("net down")),
        ), patch(
            "bot.handlers.hotspot_common.reply_final", new=AsyncMock()
        ):
            result = await search_users_for_action(_update(), _ctx(), "delete")
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_results_reprompts_for_delete(self):
        users = []
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ):
            result = await search_users_for_action(_update(), _ctx(), "delete")
        assert result == WAITING_DELETE_ID

    @pytest.mark.asyncio
    async def test_no_results_reprompts_for_edit(self):
        users = []
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ):
            result = await search_users_for_action(_update(), _ctx(), "edit")
        assert result == WAITING_EDIT_FIELD

    @pytest.mark.asyncio
    async def test_single_user_delete_goes_to_confirm(self):
        users = [{".id": "*1"}]
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ) as mock_send:
            result = await search_users_for_action(_update(), _ctx(), "delete")
        assert result == WAITING_INPUT

    @pytest.mark.asyncio
    async def test_single_user_edit_goes_to_field(self):
        users = [{".id": "*1"}]
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ) as mock_send:
            result = await search_users_for_action(_update(), _ctx(), "edit")
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_multiple_users_delete_shows_list(self):
        users = [{".id": "*1"}, {".id": "*2"}, {".id": "*3"}]
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ):
            result = await search_users_for_action(_update(), _ctx(), "delete")
        assert result == WAITING_DELETE_SELECT

    @pytest.mark.asyncio
    async def test_multiple_users_edit_shows_list(self):
        users = [{".id": "*1"}, {".id": "*2"}]
        with patch(
            "bot.handlers.hotspot_common.get_selected_router",
            return_value="discovered_1",
        ), patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(return_value=users),
        ), patch(
            "bot.handlers.hotspot_common.send_step", new=AsyncMock()
        ):
            result = await search_users_for_action(_update(), _ctx(), "edit")
        assert result == WAITING_EDIT_VALUE


class TestExecuteAddUser:
    @pytest.mark.asyncio
    async def test_success_returns_true(self):
        mock_log = MagicMock()
        with patch(
            "bot.handlers.hotspot_common.run_blocking", side_effect=[None, MagicMock()]
        ), patch("bot.handlers.hotspot_common.log_action", return_value=mock_log):
            ctx = _ctx()
            get_hotspot_add_session(ctx.user_data).username = "u1"
            get_hotspot_add_session(ctx.user_data).password = "p1"
            get_hotspot_add_session(ctx.user_data).profile = "1M"
            ok, err = await execute_add_user(ctx, ADMIN_ID, "discovered_1", "test")
        assert ok is True
        assert err is None

    @pytest.mark.asyncio
    async def test_duplicate_error_clears_state(self):
        with patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(side_effect=Exception("already have user with this name")),
        ):
            ctx = _ctx()
            get_hotspot_add_session(ctx.user_data).username = "u1"
            get_hotspot_add_session(ctx.user_data).password = "p1"
            get_hotspot_add_session(ctx.user_data).profile = "1M"
            get_hotspot_add_session(ctx.user_data).bytes_total = "1G"
            get_hotspot_add_session(ctx.user_data).uptime_value = "1d"
            get_hotspot_add_session(ctx.user_data).uptime_type = "d"
            ok, err = await execute_add_user(ctx, ADMIN_ID, "discovered_1", "test")
        assert ok is False
        assert err == "duplicate"
        assert "hotspot_add_session" not in ctx.user_data
        assert "add_bytes" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_other_error_returns_message(self):
        with patch(
            "bot.handlers.hotspot_common.run_blocking",
            new=AsyncMock(side_effect=Exception("connection timeout")),
        ):
            ctx = _ctx()
            get_hotspot_add_session(ctx.user_data).username = "u1"
            get_hotspot_add_session(ctx.user_data).password = "p1"
            get_hotspot_add_session(ctx.user_data).profile = "1M"
            ok, err = await execute_add_user(ctx, ADMIN_ID, "discovered_1", "test")
        assert ok is False
        assert "connection timeout" in (err or "")

    @pytest.mark.asyncio
    async def test_optional_fields_use_defaults(self):
        mock_run = MagicMock(side_effect=[None, MagicMock()])
        with patch(
            "bot.handlers.hotspot_common.run_blocking", side_effect=mock_run
        ), patch("database.models.log_action"):
            ctx = _ctx()
            get_hotspot_add_session(ctx.user_data).username = "u1"
            get_hotspot_add_session(ctx.user_data).profile = "1M"
            ok, err = await execute_add_user(ctx, ADMIN_ID, "discovered_1", "")
        assert ok is True
        assert err is None
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0].kwargs["password"] == ""
        assert mock_run.call_args_list[0].kwargs["bytes_total"] == ""
        assert mock_run.call_args_list[0].kwargs["uptime"] == ""
