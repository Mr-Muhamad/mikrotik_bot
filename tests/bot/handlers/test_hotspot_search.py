"""Tests for bot.handlers.hotspot_search."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_HOTSPOT_SEARCH
from bot.handlers.hotspot_search import (
    hotspot_host_action,
    hotspot_search_back,
    hotspot_search_query,
    hotspot_search_start,
    hotspot_show_host,
)
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = MagicMock()
    return ctx


def _admin_update(**kwargs):
    """Create a mock update with effective_chat.type='private' for @admin_only tests."""
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    chat = MagicMock()
    chat.type = "private"
    update.effective_chat = chat
    for k, v in kwargs.items():
        setattr(update, k, v)
    return update


class TestHotspotSearchStart:
    @pytest.mark.asyncio
    async def test_start_with_callback(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "hotspot_search"
        update.callback_query = query

        with patch("bot.handlers.hotspot_search.edit_clean", new=AsyncMock()):
            result = await hotspot_search_start(update, _ctx())
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_start_without_callback(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = None
        update.message = MagicMock()

        with patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()):
            result = await hotspot_search_start(update, _ctx())
        assert result == WAITING_HOTSPOT_SEARCH


class TestHotspotSearchQuery:
    @pytest.mark.asyncio
    async def test_no_router_ends(self):

        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private", id=1)
        update.message = MagicMock()
        update.message.text = "ali"
        context = _ctx()

        with (
            patch("bot.handlers.hotspot_search.get_selected_router", return_value=None),
            patch("bot.handlers.hotspot_search.reply_final", new=AsyncMock()) as mock_reply,
        ):
            result = await hotspot_search_query(update, context)
        assert result == ConversationHandler.END
        mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_success(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private", id=1)
        update.message = MagicMock()
        update.message.text = "ali"
        context = _ctx()

        hosts = [
            {
                "host-name": "Phone1",
                "address": "10.0.0.5",
                "mac-address": "AA:BB:CC:DD:EE:FF",
            }
        ]
        loading = MagicMock()
        loading.message_id = 999

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(return_value=hosts),
            ),
        ):
            result = await hotspot_search_query(update, context)
        assert result == WAITING_HOTSPOT_SEARCH
        assert context.user_data["search_hosts"] == hosts

    @pytest.mark.asyncio
    async def test_exception_ends(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private", id=1)
        update.message = MagicMock()
        update.message.text = "x"
        context = _ctx()

        loading = MagicMock()
        loading.message_id = 999

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(side_effect=Exception("net down")),
            ),
            patch("bot.handlers.hotspot_search.reply_final", new=AsyncMock()),
        ):
            result = await hotspot_search_query(update, context)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_no_results(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private", id=1)
        update.message = MagicMock()
        update.message.text = "nobody"
        context = _ctx()

        loading = MagicMock()
        loading.message_id = 999

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()) as mock_send,
            patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=[])),
        ):
            await hotspot_search_query(update, context)
        text = mock_send.call_args.kwargs.get("text") or mock_send.call_args.args[2]
        assert "📭" in text or "لا توجد" in text


class TestHotspotSearchBack:
    @pytest.mark.asyncio
    async def test_back_from_host_detail(self):
        update = MagicMock()
        query = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        query.answer = AsyncMock()
        query.data = "back"
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [{"host-name": "x"}]
        context.user_data["kick_host_idx"] = 0

        with patch("bot.handlers.hotspot_search.edit_clean", new=AsyncMock()):
            result = await hotspot_search_back(update, context)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "kick_host_idx" not in context.user_data

    @pytest.mark.asyncio
    async def test_back_to_prompt(self):
        update = MagicMock()
        query = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        query.answer = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [{"host-name": "x"}]

        with patch("bot.handlers.hotspot_search.edit_clean", new=AsyncMock()):
            result = await hotspot_search_back(update, context)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "search_hosts" not in context.user_data

    @pytest.mark.asyncio
    async def test_back_initial(self):
        update = MagicMock()
        query = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        query.answer = AsyncMock()
        update.callback_query = query
        context = _ctx()

        with patch("bot.handlers.hotspot_search.edit_clean", new=AsyncMock()):
            result = await hotspot_search_back(update, context)
        assert result == WAITING_HOTSPOT_SEARCH


class TestHotspotShowHost:
    @pytest.mark.asyncio
    async def test_show_host_success(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_sel_0"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [
            {
                "host-name": "Phone",
                "address": "10.0.0.5",
                "mac-address": "AA:BB:CC:DD:EE:FF",
            }
        ]

        result = await hotspot_show_host(update, context)
        assert result == WAITING_HOTSPOT_SEARCH
        assert context.user_data["kick_host_idx"] == 0

    @pytest.mark.asyncio
    async def test_show_host_uses_user_when_no_hostname(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_sel_0"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [{"user": "user1", "address": "10.0.0.6"}]

        result = await hotspot_show_host(update, context)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_show_host_invalid_index_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_sel_99"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [{"host-name": "x"}]

        result = await hotspot_show_host(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_show_host_success_returns_to_search(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_sel_0"
        query.edit_message_text = AsyncMock(return_value=None)
        query.from_user = MagicMock(id=ADMIN_ID)
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = query
        context = _ctx()
        context.user_data["search_hosts"] = [
            {"host-name": "x", "address": "10.0.0.1", "mac-address": "AA:BB"}
        ]

        result = await hotspot_show_host(update, context)
        assert result == WAITING_HOTSPOT_SEARCH


class TestHotspotHostKick:
    @pytest.mark.asyncio
    async def test_kick_success_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_kick_execute"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.callback_query = query
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        context = _ctx()
        context.user_data["search_hosts"] = [{"mac-address": "AA:BB:CC:DD:EE:FF"}]
        context.user_data["kick_host_idx"] = 0

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(return_value=(True, "Phone")),
            ),
        ):
            result = await hotspot_host_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_failure_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_kick_confirm"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.callback_query = query
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        context = _ctx()
        context.user_data["search_hosts"] = [{"mac-address": "AA:BB:CC:DD:EE:FF"}]
        context.user_data["kick_host_idx"] = 0

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(return_value=(False, "")),
            ),
        ):
            result = await hotspot_host_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_no_idx_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_kick_confirm"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.callback_query = query
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        context = _ctx()

        result = await hotspot_host_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_invalid_index_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_kick_confirm"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.callback_query = query
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        context = _ctx()
        context.user_data["search_hosts"] = []
        context.user_data["kick_host_idx"] = 5

        with patch(
            "bot.handlers.hotspot_search.get_selected_router",
            return_value="discovered_1",
        ):
            result = await hotspot_host_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_exception_ends(self):
        update = MagicMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "host_kick_confirm"
        query.edit_message_text = AsyncMock()
        query.from_user = MagicMock(id=ADMIN_ID)
        update.callback_query = query
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        context = _ctx()
        context.user_data["search_hosts"] = [{"mac-address": "AA:BB:CC:DD:EE:FF"}]
        context.user_data["kick_host_idx"] = 0

        with (
            patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(side_effect=Exception("boom")),
            ),
        ):
            result = await hotspot_host_action(update, context)
        assert result == ConversationHandler.END
