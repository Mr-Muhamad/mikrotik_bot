"""Unit tests for bot/handlers/hotspot_add.py — full add flow coverage.

These tests patch the router selector so we can test the handler logic
in isolation, without depending on the SQLite session database state.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.handlers.hotspot_add import (
    add_back_to_bytes,
    add_back_to_password,
    add_back_to_profile,
    add_back_to_uptime,
    add_back_to_uptime_from_comment,
    add_back_to_username,
    convert_uptime_value,
    get_uptime_type_keyboard,
    hotspot_add_bytes,
    hotspot_add_comment,
    hotspot_add_password,
    hotspot_add_profile,
    hotspot_add_profile_selected,
    hotspot_add_start,
    hotspot_add_uptime_type,
    hotspot_add_uptime_type_invalid_text,
    hotspot_add_uptime_value,
    hotspot_add_username,
    skip_bytes,
    skip_comment,
    skip_password,
    skip_uptime,
)
from bot.handlers.constants import (
    WAITING_BYTES_TOTAL,
    WAITING_COMMENT,
    WAITING_PASSWORD,
    WAITING_PROFILE,
    WAITING_UPTIME_TYPE,
    WAITING_UPTIME_VALUE,
    WAITING_USERNAME,
)
from telegram.ext import ConversationHandler

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update


ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _patch_router(monkeypatch):
    """Patch router_selector AND clear admin_only rate limit cache.

    Patches both the canonical module path (used by require_router's
    local import) and the local import in bot.handlers.hotspot_add
    (which does `from bot.router_selector import get_selected_router`).
    """
    router_lookup = lambda uid: "discovered_1" if uid == ADMIN_ID else None  # noqa: E731

    # Patch in bot.router_selector (used by require_router local import)
    monkeypatch.setattr("bot.router_selector.get_selected_router", router_lookup)
    monkeypatch.setattr("bot.router_selector.set_selected_router", lambda uid, key: None)
    monkeypatch.setattr("bot.router_selector.set_current_action",
                        lambda uid, action, data=None: None)
    monkeypatch.setattr("bot.router_selector.clear_action", lambda uid: None)
    monkeypatch.setattr("bot.router_selector.clear_router", lambda uid: None)
    # Patch the local import in bot.handlers.hotspot_add
    monkeypatch.setattr("bot.handlers.hotspot_add.get_selected_router", router_lookup)
    # Clear rate-limit cache so consecutive tests aren't blocked
    from utils.admin_decorator import _rate_limit_data
    _rate_limit_data.clear()


# ─── Helper function tests ────────────────────────────────────


class TestGetUptimeTypeKeyboard:
    def test_returns_keyboard(self):
        kb = get_uptime_type_keyboard()
        assert kb is not None


class TestConvertUptimeValue:
    def test_hours_valid(self):
        assert convert_uptime_value("5", "hours") == "05:00:00"
        assert convert_uptime_value("12", "hours") == "12:00:00"

    def test_days_valid(self):
        assert convert_uptime_value("7", "days") == "7d00:00:00"

    def test_invalid_returns_empty(self):
        assert convert_uptime_value("abc", "hours") == ""
        assert convert_uptime_value("", "hours") == ""
        assert convert_uptime_value("-5", "hours") == ""
        assert convert_uptime_value("0", "hours") == ""


# ─── hotspot_add_start tests ──────────────────────────────────


class TestHotspotAddStart:
    @pytest.mark.asyncio
    async def test_start_with_callback(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hotspot_add")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.nav_set"):
            result = await hotspot_add_start(u, c)
        assert result == WAITING_USERNAME
        u.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_message(self):
        u = make_mock_update(user_id=ADMIN_ID, text="/start")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.nav_set"):
            result = await hotspot_add_start(u, c)
        assert result == WAITING_USERNAME


# ─── hotspot_add_username tests ───────────────────────────────


class TestHotspotAddUsername:
    @pytest.mark.asyncio
    async def test_valid_username_advances(self):
        u = make_mock_update(user_id=ADMIN_ID, text="user1")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.hotspot_manager.user_exists",
                   new=Mock(return_value=False)):
            result = await hotspot_add_username(u, c)
        assert result == WAITING_PASSWORD
        assert c.user_data["add_username"] == "user1"

    @pytest.mark.asyncio
    async def test_existing_username_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="user1")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.hotspot_manager.user_exists",
                   new=Mock(return_value=True)):
            result = await hotspot_add_username(u, c)
        assert result == WAITING_USERNAME
        assert "add_username" not in c.user_data

    @pytest.mark.asyncio
    async def test_invalid_username_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="ab")
        c = make_mock_context()
        result = await hotspot_add_username(u, c)
        assert result == WAITING_USERNAME
        assert "add_username" not in c.user_data


# ─── hotspot_add_password tests ───────────────────────────────


class TestHotspotAddPassword:
    @pytest.mark.asyncio
    async def test_valid_password_with_profiles(self):
        u = make_mock_update(user_id=ADMIN_ID, text="12345")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(return_value=[{"name": "default"}, {"name": "premium"}])):
            result = await hotspot_add_password(u, c)
        assert result == WAITING_PROFILE
        assert c.user_data["add_password"] == "12345"

    @pytest.mark.asyncio
    async def test_invalid_password_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="ab")
        c = make_mock_context()
        result = await hotspot_add_password(u, c)
        assert result == WAITING_PASSWORD
        assert "add_password" not in c.user_data

    @pytest.mark.asyncio
    async def test_profiles_failure_ends_conversation(self):
        u = make_mock_update(user_id=ADMIN_ID, text="12345")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(side_effect=Exception("router offline"))):
            with patch("bot.handlers.hotspot_add.send_error",
                       new=AsyncMock()) as mock_send_error:
                result = await hotspot_add_password(u, c)
        assert result == ConversationHandler.END
        mock_send_error.assert_called_once()
        call_kwargs = mock_send_error.call_args.kwargs
        assert call_kwargs["router_key"] == "discovered_1"


# ─── hotspot_add_profile tests ────────────────────────────────


class TestHotspotAddProfile:
    @pytest.mark.asyncio
    async def test_valid_profile_advances(self):
        u = make_mock_update(user_id=ADMIN_ID, text="default")
        c = make_mock_context()
        result = await hotspot_add_profile(u, c)
        assert result == WAITING_BYTES_TOTAL
        assert c.user_data["add_profile"] == "default"


# ─── hotspot_add_profile_selected tests ───────────────────────


class TestHotspotAddProfileSelected:
    @pytest.mark.asyncio
    async def test_valid_profile_callback_advances(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_profile_premium")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.resolve_profile_from_callback",
                   return_value="premium"):
            result = await hotspot_add_profile_selected(u, c)
        assert result == WAITING_BYTES_TOTAL
        assert c.user_data["add_profile"] == "premium"

    @pytest.mark.asyncio
    async def test_invalid_profile_callback_ends(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_profile_X")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.resolve_profile_from_callback", return_value=None):
            result = await hotspot_add_profile_selected(u, c)
        assert result == ConversationHandler.END


# ─── hotspot_add_bytes tests ──────────────────────────────────


class TestHotspotAddBytes:
    @pytest.mark.asyncio
    async def test_valid_bytes_advances(self):
        u = make_mock_update(user_id=ADMIN_ID, text="1G")
        c = make_mock_context()
        result = await hotspot_add_bytes(u, c)
        assert result == WAITING_UPTIME_TYPE
        assert c.user_data["add_bytes"]

    @pytest.mark.asyncio
    async def test_invalid_bytes_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="garbage!!!")
        c = make_mock_context()
        result = await hotspot_add_bytes(u, c)
        assert result == WAITING_BYTES_TOTAL
        assert "add_bytes" not in c.user_data


# ─── hotspot_add_comment tests ────────────────────────────────


class TestHotspotAddComment:
    @pytest.mark.asyncio
    async def test_successful_add(self):
        u = make_mock_update(user_id=ADMIN_ID, text="my comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(True, None))):
            with patch("bot.handlers.hotspot_add.reply_final",
                       new=AsyncMock()) as mock_reply:
                result = await hotspot_add_comment(u, c)
        assert result == ConversationHandler.END
        mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_reprompts_username(self):
        u = make_mock_update(user_id=ADMIN_ID, text="my comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(False, "duplicate"))):
            with patch("bot.handlers.hotspot_add.send_step", new=AsyncMock()):
                result = await hotspot_add_comment(u, c)
        assert result == WAITING_USERNAME

    @pytest.mark.asyncio
    async def test_error_replies_with_error_msg(self):
        u = make_mock_update(user_id=ADMIN_ID, text="my comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(False, "connection failed"))):
            with patch("bot.handlers.hotspot_add.reply_final",
                       new=AsyncMock()) as mock_reply:
                result = await hotspot_add_comment(u, c)
        assert result == ConversationHandler.END
        mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_router_selected_ends(self, monkeypatch):
        # Override fixture: no router for this test
        monkeypatch.setattr(
            "bot.router_selector.get_selected_router",
            lambda uid: None,
        )
        u = make_mock_update(user_id=ADMIN_ID, text="my comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.reply_final", new=AsyncMock()):
            result = await hotspot_add_comment(u, c)
        assert result == ConversationHandler.END


# ─── Back navigation tests ────────────────────────────────────


class TestBackNavigation:
    @pytest.mark.asyncio
    async def test_back_to_username(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_username")
        c = make_mock_context()
        result = await add_back_to_username(u, c)
        assert result == WAITING_USERNAME

    @pytest.mark.asyncio
    async def test_back_to_password(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_password")
        c = make_mock_context()
        result = await add_back_to_password(u, c)
        assert result == WAITING_PASSWORD

    @pytest.mark.asyncio
    async def test_back_to_profile_success(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_profile")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(return_value=[{"name": "default"}])):
            result = await add_back_to_profile(u, c)
        assert result == WAITING_PROFILE

    @pytest.mark.asyncio
    async def test_back_to_profile_failure(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_profile")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(side_effect=Exception("net err"))):
            with patch("bot.handlers.hotspot_add.send_error", new=AsyncMock()):
                result = await add_back_to_profile(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_back_to_bytes(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_bytes")
        c = make_mock_context()
        result = await add_back_to_bytes(u, c)
        assert result == WAITING_BYTES_TOTAL

    @pytest.mark.asyncio
    async def test_back_to_uptime_from_comment(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_uptime")
        c = make_mock_context()
        result = await add_back_to_uptime_from_comment(u, c)
        assert result == WAITING_UPTIME_TYPE

    @pytest.mark.asyncio
    async def test_back_to_uptime(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="add_back_to_uptime")
        c = make_mock_context()
        result = await add_back_to_uptime(u, c)
        assert result == WAITING_UPTIME_TYPE


# ─── Skip handler tests ───────────────────────────────────────


class TestSkipHandlers:
    @pytest.mark.asyncio
    async def test_skip_password(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_password")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(return_value=[{"name": "default"}])):
            result = await skip_password(u, c)
        assert result == WAITING_PROFILE
        assert c.user_data["add_password"] == ""

    @pytest.mark.asyncio
    async def test_skip_password_profiles_failure(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_password")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.fetch_and_cache_profiles",
                   new=AsyncMock(side_effect=Exception("err"))):
            with patch("bot.handlers.hotspot_add.send_error", new=AsyncMock()):
                result = await skip_password(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_skip_bytes(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_bytes")
        c = make_mock_context()
        result = await skip_bytes(u, c)
        assert result == WAITING_UPTIME_TYPE
        assert c.user_data["add_bytes"] == ""

    @pytest.mark.asyncio
    async def test_skip_uptime(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_uptime")
        c = make_mock_context()
        result = await skip_uptime(u, c)
        assert result == WAITING_COMMENT
        assert c.user_data["add_uptime"] == ""


# ─── Uptime type selection tests ──────────────────────────────


class TestUptimeType:
    @pytest.mark.asyncio
    async def test_select_hours(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_hours")
        c = make_mock_context()
        result = await hotspot_add_uptime_type(u, c)
        assert result == WAITING_UPTIME_VALUE
        assert c.user_data["uptime_unit"] == "hours"

    @pytest.mark.asyncio
    async def test_select_days(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_days")
        c = make_mock_context()
        result = await hotspot_add_uptime_type(u, c)
        assert result == WAITING_UPTIME_VALUE
        assert c.user_data["uptime_unit"] == "days"

    @pytest.mark.asyncio
    async def test_select_skip(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_uptime")
        c = make_mock_context()
        result = await hotspot_add_uptime_type(u, c)
        assert result == WAITING_COMMENT
        assert c.user_data["add_uptime"] == ""

    @pytest.mark.asyncio
    async def test_unknown_data_stays(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_unknown")
        c = make_mock_context()
        result = await hotspot_add_uptime_type(u, c)
        assert result == WAITING_UPTIME_TYPE


# ─── Uptime value tests ───────────────────────────────────────


class TestUptimeValue:
    @pytest.mark.asyncio
    async def test_valid_value_advances(self):
        u = make_mock_update(user_id=ADMIN_ID, text="5")
        c = make_mock_context()
        c.user_data["uptime_unit"] = "hours"
        result = await hotspot_add_uptime_value(u, c)
        assert result == WAITING_COMMENT
        assert c.user_data["add_uptime"] == "05:00:00"

    @pytest.mark.asyncio
    async def test_invalid_value_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="xyz")
        c = make_mock_context()
        c.user_data["uptime_unit"] = "hours"
        result = await hotspot_add_uptime_value(u, c)
        assert result == WAITING_UPTIME_VALUE
        assert "add_uptime" not in c.user_data


# ─── skip_comment tests ───────────────────────────────────────


class TestSkipComment:
    @pytest.mark.asyncio
    async def test_skip_with_no_router(self, monkeypatch):
        # Override fixture: make get_selected_router return None for this test
        monkeypatch.setattr(
            "bot.router_selector.get_selected_router",
            lambda uid: None,
        )
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_comment")
        c = make_mock_context()
        result = await skip_comment(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_skip_successful(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(True, None))):
            result = await skip_comment(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_skip_duplicate(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(False, "duplicate"))):
            result = await skip_comment(u, c)
        assert result == WAITING_USERNAME

    @pytest.mark.asyncio
    async def test_skip_error(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="skip_comment")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.execute_add_user",
                   new=AsyncMock(return_value=(False, "connection lost"))):
            result = await skip_comment(u, c)
        assert result == ConversationHandler.END


# ─── Invalid text handler test ────────────────────────────────


class TestInvalidTextHandler:
    @pytest.mark.asyncio
    async def test_invalid_text_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="some text")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_add.send_step", new=AsyncMock()) as mock_send:
            result = await hotspot_add_uptime_type_invalid_text(u, c)
        assert result == WAITING_UPTIME_TYPE
        mock_send.assert_called_once()
