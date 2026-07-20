"""Integration-style tests for the Hotspot host search flow.

Tests the search through handlers using the in-memory MikrotikAPIMock.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.hotspot_search import (
    hotspot_search_query,
    hotspot_search_start,
)
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774
ROUTER_KEY = "discovered_1"


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
    return context


class TestHotspotSearchStart:
    @pytest.mark.asyncio
    async def test_start_prompts_for_term(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_HOTSPOT_SEARCH
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="/search")
        context = _make_context()

        result = await hotspot_search_start(update, context)
        assert result == WAITING_HOTSPOT_SEARCH


class TestHotspotSearchQuery:
    @pytest.mark.asyncio
    async def test_search_no_router_ends(self, mock_mikrotik_api):
        from bot.router_selector import clear_router

        clear_router(ADMIN_ID)
        update = make_mock_update(text="any")
        context = _make_context()

        result = await hotspot_search_query(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_HOTSPOT_SEARCH
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="AA:BB:CC")
        context = _make_context()
        mock_loading = MagicMock()
        mock_loading.message_id = 999

        with (
            patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=mock_loading),
            ),
            patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
        ):
            result = await hotspot_search_query(update, context)

        assert result == WAITING_HOTSPOT_SEARCH
        assert "search_hosts" in context.user_data

    @pytest.mark.asyncio
    async def test_search_error_ends_conversation(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_HOTSPOT_SEARCH
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="any")
        context = _make_context()
        mock_loading = MagicMock()
        mock_loading.message_id = 999

        with (
            patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=mock_loading),
            ),
            patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()),
            patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(side_effect=Exception("timeout")),
            ),
        ):
            result = await hotspot_search_query(update, context)

        assert result == WAITING_HOTSPOT_SEARCH
