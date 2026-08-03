"""Tests for bot/handlers/menus.py - go_back and end_conversation handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.menus"

MOCK_NAV_TARGETS = {
    "main_menu": AsyncMock(),
    "menu_hotspot": AsyncMock(),
    "menu_userman": AsyncMock(),
    "menu_stats": AsyncMock(),
    "menu_backup": AsyncMock(),
    "menu_pdf_settings": AsyncMock(),
    "menu_routers": AsyncMock(),
    "menu_reports": AsyncMock(),
}


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_get", return_value="menu_hotspot"))
    stack.enter_context(patch(f"{P}.NAV_TARGETS", MOCK_NAV_TARGETS))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestGoBack:
    @pytest.mark.asyncio
    async def test_returns_conversation_end(self):
        from bot.handlers.menus import go_back

        update = make_mock_update(callback_data="back")
        context = make_mock_context()
        result = await go_back(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch(f"{P}.resolve_nav_target")
    @patch(f"{P}.nav_get", return_value="menu_stats")
    async def test_resolves_nav_target(self, mock_nav_get, mock_resolve):  # type: ignore[reportMissingParameterType]
        from bot.handlers.menus import go_back

        mock_resolve.return_value = AsyncMock()
        update = make_mock_update(callback_data="back")
        context = make_mock_context()
        await go_back(update, context)
        mock_nav_get.assert_called_once_with(context)
        mock_resolve.assert_called_once_with("menu_stats")

    @pytest.mark.asyncio
    @patch(f"{P}.resolve_nav_target")
    @patch(f"{P}.nav_get", return_value="main_menu")
    async def test_calls_resolved_handler(self, mock_nav_get, mock_resolve):  # type: ignore[reportMissingParameterType]
        from bot.handlers.menus import go_back

        mock_handler = AsyncMock()
        mock_resolve.return_value = mock_handler
        update = make_mock_update(callback_data="back")
        context = make_mock_context()
        await go_back(update, context)
        mock_handler.assert_called_once_with(update, context)


class TestEndConversation:
    @pytest.mark.asyncio
    async def test_returns_conversation_end(self):
        from bot.handlers.menus import end_conversation

        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        result = await end_conversation(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_calls_cleanup_state(self):
        from bot.handlers.menus import end_conversation

        update = make_mock_update(callback_data="cancel", user_id=724730774)
        context = make_mock_context()
        await end_conversation(update, context, "menu_hotspot")
        from bot.handlers.menus import cleanup_state

        cleanup_state.assert_called_once_with(724730774, context.user_data)  # type: ignore[reportFunctionMemberAccess]

    @pytest.mark.asyncio
    @patch(f"{P}.NAV_TARGETS")
    async def test_calls_target_handler(self, mock_targets):  # type: ignore[reportMissingParameterType]
        from bot.handlers.menus import end_conversation

        mock_handler = AsyncMock()
        mock_targets.__getitem__ = lambda self, key: mock_handler
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        await end_conversation(update, context, "menu_backup")
        mock_handler.assert_called_once_with(update, context)

    @pytest.mark.asyncio
    async def test_defaults_to_main_menu(self):
        from bot.handlers.menus import end_conversation

        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        result = await end_conversation(update, context)
        assert result == ConversationHandler.END


class TestEndConversationToMain:
    @pytest.mark.asyncio
    async def test_returns_conversation_end(self):
        from bot.handlers.menus import end_conversation_to_main

        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        result = await end_conversation_to_main(update, context)
        assert result == ConversationHandler.END


class TestEndConversationToHotspot:
    @pytest.mark.asyncio
    async def test_returns_conversation_end(self):
        from bot.handlers.menus import end_conversation_to_hotspot

        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        result = await end_conversation_to_hotspot(update, context)
        assert result == ConversationHandler.END


class TestResolveNavTarget:
    @patch(f"{P}.NAV_TARGETS", {"menu_hotspot": "handler_stub"})
    @patch(f"{P}.internal_main_menu", "fallback_stub")
    def test_returns_nav_target_when_found(self):
        from bot.handlers.menus import resolve_nav_target

        result = resolve_nav_target("menu_hotspot")
        assert result == "handler_stub"

    @patch(f"{P}.NAV_TARGETS", {})
    @patch(f"{P}.sr", "saved_routers_stub")
    @patch(f"{P}.internal_main_menu", "fallback_stub")
    def test_returns_saved_routers_for_saved_routers(self):
        from bot.handlers.menus import resolve_nav_target

        result = resolve_nav_target("saved_routers")
        assert result == "saved_routers_stub"

    @patch(f"{P}.NAV_TARGETS", {})
    @patch(f"{P}.internal_main_menu", "fallback_stub")
    def test_falls_back_to_main_menu(self):
        from bot.handlers.menus import resolve_nav_target

        result = resolve_nav_target("unknown_target")
        assert result == "fallback_stub"
