"""Extended tests for bot/handlers/menus.py — cover internal_* functions,
main_menu with message, backup_menu/pdf_settings_menu with message paths,
and all end_conversation_to_* variants."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.menus"


@pytest.fixture(autouse=True)
def _all_patches():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    with ExitStack() as stack:
        stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
        stack.enter_context(patch(f"{P}.cleanup_state"))
        stack.enter_context(patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock))
        stack.enter_context(patch(f"{P}.send_and_track", new_callable=AsyncMock))
        stack.enter_context(patch(f"{P}.show_menu", new_callable=AsyncMock))
        stack.enter_context(patch(f"{P}.get_selected_router", return_value="discovered_1"))
        stack.enter_context(patch(f"{P}.get_router_part", new_callable=AsyncMock))
        stack.enter_context(patch(f"{P}._get_router_system_part", new_callable=AsyncMock))
        yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestMainMenu:
    @pytest.mark.asyncio
    async def test_with_callback_query(self):
        update = make_mock_update(callback_data="main_menu")
        context = make_mock_context()
        from bot.handlers.menus import main_menu

        result = await main_menu(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_with_message(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.menus import main_menu

        result = await main_menu(update, context)
        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once()


class TestBackupMenu:
    @pytest.mark.asyncio
    async def test_with_callback_query(self):
        update = make_mock_update(callback_data="backup")
        context = make_mock_context()
        from bot.handlers.menus import backup_menu

        await backup_menu(update, context)

    @pytest.mark.asyncio
    async def test_with_message(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.menus import backup_menu

        await backup_menu(update, context)


class TestPdfSettingsMenu:
    @pytest.mark.asyncio
    async def test_with_callback_query(self):
        update = make_mock_update(callback_data="pdf_settings")
        context = make_mock_context()
        from bot.handlers.menus import pdf_settings_menu

        await pdf_settings_menu(update, context)

    @pytest.mark.asyncio
    async def test_with_message(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.menus import pdf_settings_menu

        await pdf_settings_menu(update, context)


class TestEndConversationToVariants:
    @pytest.mark.asyncio
    async def test_to_stats(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import end_conversation_to_stats

        result = await end_conversation_to_stats(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_to_backup(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import end_conversation_to_backup

        result = await end_conversation_to_backup(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_to_pdf_settings(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import end_conversation_to_pdf_settings

        result = await end_conversation_to_pdf_settings(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_to_routers(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import end_conversation_to_routers

        result = await end_conversation_to_routers(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_to_reports(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import end_conversation_to_reports

        result = await end_conversation_to_reports(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_to_userman(self):
        update = make_mock_update(callback_data="cancel")
        context = make_mock_context()
        from bot.handlers.menus import menu_userman_from_conversation

        result = await menu_userman_from_conversation(update, context)
        assert result == ConversationHandler.END


class TestInternalMenuFunctions:
    @pytest.mark.asyncio
    async def test_internal_hotspot_menu(self):
        update = make_mock_update(callback_data="hotspot")
        context = make_mock_context()
        from bot.handlers.menus import internal_hotspot_menu

        await internal_hotspot_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_userman_menu(self):
        update = make_mock_update(callback_data="userman")
        context = make_mock_context()
        from bot.handlers.menus import internal_userman_menu

        await internal_userman_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_stats_menu(self):
        update = make_mock_update(callback_data="stats")
        context = make_mock_context()
        from bot.handlers.menus import internal_stats_menu

        await internal_stats_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_backup_menu(self):
        update = make_mock_update(callback_data="backup")
        context = make_mock_context()
        from bot.handlers.menus import internal_backup_menu

        await internal_backup_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_routers_menu(self):
        update = make_mock_update(callback_data="routers")
        context = make_mock_context()
        from bot.handlers.menus import internal_routers_menu

        await internal_routers_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_reports_menu(self):
        update = make_mock_update(callback_data="reports")
        context = make_mock_context()
        from bot.handlers.menus import internal_reports_menu

        await internal_reports_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_pdf_settings_menu(self):
        update = make_mock_update(callback_data="pdf")
        context = make_mock_context()
        from bot.handlers.menus import internal_pdf_settings_menu

        await internal_pdf_settings_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_main_menu_with_query(self):
        update = make_mock_update(callback_data="main")
        context = make_mock_context()
        from bot.handlers.menus import internal_main_menu

        await internal_main_menu(update, context)

    @pytest.mark.asyncio
    async def test_internal_main_menu_without_query(self):
        update = make_mock_update()
        context = make_mock_context()
        from bot.handlers.menus import internal_main_menu

        await internal_main_menu(update, context)


class TestAllMenuHandlers:
    @pytest.mark.asyncio
    async def test_hotspot_menu(self):
        update = make_mock_update(callback_data="hotspot")
        context = make_mock_context()
        from bot.handlers.menus import hotspot_menu

        await hotspot_menu(update, context)

    @pytest.mark.asyncio
    async def test_userman_menu(self):
        update = make_mock_update(callback_data="userman")
        context = make_mock_context()
        from bot.handlers.menus import userman_menu

        await userman_menu(update, context)

    @pytest.mark.asyncio
    async def test_stats_menu(self):
        update = make_mock_update(callback_data="stats")
        context = make_mock_context()
        from bot.handlers.menus import stats_menu

        await stats_menu(update, context)

    @pytest.mark.asyncio
    async def test_routers_menu(self):
        update = make_mock_update(callback_data="routers")
        context = make_mock_context()
        from bot.handlers.menus import routers_menu

        await routers_menu(update, context)

    @pytest.mark.asyncio
    async def test_reports_menu(self):
        update = make_mock_update(callback_data="reports")
        context = make_mock_context()
        from bot.handlers.menus import reports_menu

        await reports_menu(update, context)
