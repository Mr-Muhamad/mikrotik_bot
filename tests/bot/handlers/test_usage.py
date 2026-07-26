"""Tests for bot/handlers/usage.py - Hotspot usage report flow."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.usage"


async def _call_through(fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_error", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_selected_router"))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.hotspot_manager"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestUsageStart:
    @pytest.mark.asyncio
    async def test_returns_waiting_state_when_router_selected(self):
        from bot.handlers.usage import usage_start
        from bot.handlers.constants import WAITING_USAGE_QUERY

        with patch(f"{P}.get_selected_router", return_value="router_1"):
            result = await usage_start(
                make_mock_update(callback_data="usage"),
                make_mock_context(),
            )
        assert result == WAITING_USAGE_QUERY

    @pytest.mark.asyncio
    async def test_ends_conversation_when_no_router(self):
        from bot.handlers.usage import usage_start
        from telegram.ext import ConversationHandler

        with patch(f"{P}.get_selected_router", return_value=None):
            result = await usage_start(
                make_mock_update(callback_data="usage"),
                make_mock_context(),
            )
        assert result == ConversationHandler.END


class TestUsageQuery:
    @pytest.mark.asyncio
    async def test_successful_search_returns_report(self):
        from bot.handlers.usage import usage_query
        from telegram.ext import ConversationHandler

        ctx = make_mock_context()
        ctx.user_data["usage_router"] = "router_1"

        mock_user = {
            "name": "testuser",
            "disabled": "false",
            "profile": "default",
            "password": "pass",
            "comment": "",
            "server": "hs1",
            "bytes-in": "1024",
            "bytes-out": "2048",
            "limit-bytes-total": "",
            "limit-uptime": "",
        }
        with patch(f"{P}.hotspot_manager") as mock_hm, \
             patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through):
            mock_hm.search_users = AsyncMock(return_value=[mock_user])
            mock_hm.search_hosts = AsyncMock(return_value=[])
            result = await usage_query(
                make_mock_update(text="testuser"),
                ctx,
            )
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_search_no_results_shows_user_not_found(self):
        from bot.handlers.usage import usage_query
        from bot.handlers.constants import WAITING_USAGE_QUERY

        ctx = make_mock_context()
        ctx.user_data["usage_router"] = "router_1"

        with patch(f"{P}.hotspot_manager") as mock_hm, \
             patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through):
            mock_hm.search_users = AsyncMock(return_value=[])
            result = await usage_query(
                make_mock_update(text="nobody"),
                ctx,
            )
        assert result == WAITING_USAGE_QUERY

    @pytest.mark.asyncio
    async def test_search_failure_sends_error(self):
        from bot.handlers.usage import usage_query
        from telegram.ext import ConversationHandler

        ctx = make_mock_context()
        ctx.user_data["usage_router"] = "router_1"

        with patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=Exception("conn fail")), \
             patch(f"{P}.send_error", new_callable=AsyncMock) as mock_err:
            result = await usage_query(
                make_mock_update(text="testuser"),
                ctx,
            )
        assert result == ConversationHandler.END
        mock_err.assert_awaited_once()
