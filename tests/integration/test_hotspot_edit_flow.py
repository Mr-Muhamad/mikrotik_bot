"""Integration-style tests for the Hotspot user edit flow.

Tests the end-to-end edit flow through handlers using the in-memory
MikrotikAPIMock, simulating real MikroTik API interactions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.hotspot_edit import (
    hotspot_edit_field,
    hotspot_edit_select,
    hotspot_edit_start,
    hotspot_edit_value,
)
from bot.handlers.session_models import get_hotspot_edit_session
from core.hotspot_manager import hotspot_manager
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


def _seed_user(name="edit_user", uid_hint="*99"):
    hotspot_manager.add_user(ROUTER_KEY, name=name, password="1234", profile="default")
    users = hotspot_manager.search_users(ROUTER_KEY, name)
    if users:
        return users[0]
    return None


class TestHotspotEditStart:
    @pytest.mark.asyncio
    async def test_start_prompts_for_search(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_FIELD
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="hotspot_edit")
        context = _make_context()

        result = await hotspot_edit_start(update, context)

        assert result == WAITING_EDIT_FIELD


class TestHotspotEditSelect:
    @pytest.mark.asyncio
    async def test_select_user_populates_edit_state(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("editme")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(callback_data=f"edit_user_{uid}")
        context = _make_context()

        result = await hotspot_edit_select(update, context)

        assert result == WAITING_EDIT_VALUE
        assert get_hotspot_edit_session(context.user_data).user_id == uid
        assert get_hotspot_edit_session(context.user_data).user_data == user

    @pytest.mark.asyncio
    async def test_select_nonexistent_user_ends(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="edit_user_*9999")
        context = _make_context()

        result = await hotspot_edit_select(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_select_error_calls_send_error(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="edit_user_*1")
        context = _make_context()

        with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
            with patch(
                "bot.handlers.hotspot_edit.run_blocking",
                new=AsyncMock(side_effect=Exception("err")),
            ):
                result = await hotspot_edit_select(update, context)
        assert result == ConversationHandler.END
        mock_err.assert_called_once()


class TestHotspotEditField:
    @pytest.mark.asyncio
    async def test_select_password_field_prompts_for_value(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("pwme")
        update = make_mock_update(callback_data="edit_field_password")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).user_data = user
        get_hotspot_edit_session(context.user_data).user_id = user[".id"]

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_select_profile_field_loads_profiles(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("profme")
        update = make_mock_update(callback_data="edit_field_profile")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).user_data = user
        get_hotspot_edit_session(context.user_data).user_id = user[".id"]

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE
        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_profile_fetch_error_calls_send_error(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("prof_err")
        update = make_mock_update(callback_data="edit_field_profile")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).user_data = user
        get_hotspot_edit_session(context.user_data).user_id = user[".id"]

        with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
            with patch(
                "bot.handlers.hotspot_edit.fetch_and_cache_profiles",
                new=AsyncMock(side_effect=Exception("net")),
            ):
                result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE
        mock_err.assert_called_once()


class TestHotspotEditValue:
    @pytest.mark.asyncio
    async def test_update_password_persists(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("updme")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(text="newpass")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).current_field = "password"
        get_hotspot_edit_session(context.user_data).user_id = uid
        get_hotspot_edit_session(context.user_data).user_data = dict(user)

        result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

        updated = hotspot_manager.get_user(ROUTER_KEY, uid)
        assert updated.get("password") == "newpass"

    @pytest.mark.asyncio
    async def test_update_profile_persists(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("profupd")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(text="premium")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).current_field = "profile"
        get_hotspot_edit_session(context.user_data).user_id = uid
        get_hotspot_edit_session(context.user_data).user_data = dict(user)

        result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

        updated = hotspot_manager.get_user(ROUTER_KEY, uid)
        assert updated.get("profile") == "premium"

    @pytest.mark.asyncio
    async def test_update_bytes_persists(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("bytesupd")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(text="1G")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).current_field = "bytes"
        get_hotspot_edit_session(context.user_data).user_id = uid
        get_hotspot_edit_session(context.user_data).user_data = dict(user)

        result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

        updated = hotspot_manager.get_user(ROUTER_KEY, uid)
        assert updated.get("limit-bytes-total") == "1000000000"

    @pytest.mark.asyncio
    async def test_update_without_context_data_ends(self, mock_mikrotik_api):
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="newpass")
        context = _make_context()
        context.user_data.clear()

        result = await hotspot_edit_value(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_update_error_calls_send_error(self, mock_mikrotik_api):
        from bot.handlers.constants import WAITING_EDIT_VALUE
        from database.models import save_user_session

        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("errupd")
        assert user is not None
        uid = user[".id"]
        update = make_mock_update(text="newpass")
        context = _make_context()
        get_hotspot_edit_session(context.user_data).current_field = "password"
        get_hotspot_edit_session(context.user_data).user_id = uid
        get_hotspot_edit_session(context.user_data).user_data = dict(user)

        with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
            with patch(
                "bot.handlers.hotspot_edit.run_blocking",
                new=AsyncMock(side_effect=Exception("net")),
            ):
                result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE
        mock_err.assert_called_once()
