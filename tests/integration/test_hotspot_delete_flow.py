"""Integration-style tests for the Hotspot user delete flow.

Tests the end-to-end delete flow through handlers using the in-memory
MikrotikAPIMock, simulating real MikroTik API interactions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_DELETE_ID, WAITING_INPUT
from bot.handlers.hotspot_delete import (
    confirm_callback,
    hotspot_delete_select,
    hotspot_delete_start,
)
from bot.router_selector import cleanup_state
from core.hotspot_manager import hotspot_manager
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator
from utils.callback_utils import _CALLBACK_DEDUP

ADMIN_ID = 724730774
ROUTER_KEY = "discovered_1"


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    _CALLBACK_DEDUP.clear()
    yield
    admin_decorator._rate_limit_data.clear()
    _CALLBACK_DEDUP.clear()


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _seed_user(name="del_user", uid="*1"):
    hotspot_manager.add_user(ROUTER_KEY, name=name, password="1234", profile="default")
    users = hotspot_manager.search_users(ROUTER_KEY, name)
    if users:
        return users[0]
    return None


class TestHotspotDeleteStart:
    @pytest.mark.asyncio
    async def test_start_prompts_for_user_id(self, mock_mikrotik_api):
        from database.models import get_user_session, save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        try:
            update = make_mock_update(callback_data="hotspot_delete")
            context = _make_context()

            result = await hotspot_delete_start(update, context)

            assert result == WAITING_DELETE_ID
            session = get_user_session(ADMIN_ID)
            assert session["selected_router"] == ROUTER_KEY
        finally:
            cleanup_state(ADMIN_ID, {})

    @pytest.mark.asyncio
    async def test_start_clears_conversation_state(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="hotspot_delete")
        context = _make_context()
        context.user_data["delete_user_id"] = "stale"
        context.user_data["edit_field"] = "stale"

        await hotspot_delete_start(update, context)
        assert "delete_user_id" not in context.user_data
        assert "edit_field" not in context.user_data


class TestHotspotDeleteSelect:
    @pytest.mark.asyncio
    async def test_delete_user_shows_confirm(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("selectme")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(callback_data=f"delete_user_{uid}")
        context = _make_context()

        result = await hotspot_delete_select(update, context)

        assert result == WAITING_INPUT
        assert context.user_data.get("delete_user_id") == uid
        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user_ends_conversation(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="delete_user_*9999")
        context = _make_context()

        result = await hotspot_delete_select(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_delete_error_path_calls_send_error(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("errorme")
        uid = user[".id"]
        update = make_mock_update(callback_data=f"delete_user_{uid}")
        context = _make_context()

        with patch("bot.handlers.hotspot_delete.send_error", new=AsyncMock()) as mock_err:
            with patch(
                "bot.handlers.hotspot_delete.run_blocking",
                new=AsyncMock(side_effect=Exception("boom")),
            ):
                result = await hotspot_delete_select(update, context)

        assert result == ConversationHandler.END
        mock_err.assert_called_once()
        assert "boom" in str(mock_err.call_args)


class TestConfirmCallback:
    @pytest.mark.asyncio
    async def test_confirm_yes_deletes_user(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("confirmme")
        uid = user[".id"]
        update = make_mock_update(callback_data="confirm_yes")
        context = _make_context()
        context.user_data["delete_user_id"] = uid

        result = await confirm_callback(update, context)

        assert result == ConversationHandler.END
        assert hotspot_manager.get_user(ROUTER_KEY, uid) is None

    @pytest.mark.asyncio
    async def test_confirm_no_keeps_user(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("keepme")
        uid = user[".id"]
        update = make_mock_update(callback_data="confirm_no")
        context = _make_context()
        context.user_data["delete_user_id"] = uid

        result = await confirm_callback(update, context)

        assert result == ConversationHandler.END
        assert hotspot_manager.get_user(ROUTER_KEY, uid) is not None

    @pytest.mark.asyncio
    async def test_confirm_without_context_data_ends(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="confirm_yes")
        context = _make_context()
        context.user_data.clear()

        result = await confirm_callback(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_yes_delete_failure_calls_send_error(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("failme")
        uid = user[".id"]
        update = make_mock_update(callback_data="confirm_yes")
        context = _make_context()
        context.user_data["delete_user_id"] = uid

        with patch("bot.handlers.hotspot_delete.send_error", new=AsyncMock()) as mock_err:
            with patch(
                "bot.handlers.hotspot_delete.run_blocking",
                new=AsyncMock(side_effect=Exception("net down")),
            ):
                await confirm_callback(update, context)

        mock_err.assert_called_once()
        assert "net down" in str(mock_err.call_args)
