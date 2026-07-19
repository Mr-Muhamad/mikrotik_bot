"""Unit tests for bot/handlers/hotspot_cards.py — card generation flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_BYTES,
    WAITING_HOTSPOT_CARD_COUNT,
    WAITING_HOTSPOT_CARD_LENGTH,
    WAITING_HOTSPOT_CARD_PREFIX,
    WAITING_HOTSPOT_CARD_PROFILE,
    WAITING_HOTSPOT_CARD_TYPE,
    WAITING_HOTSPOT_CARD_UPTIME,
)
from bot.handlers.hotspot_cards import (
    _create_cards,
    get_card_type_keyboard,
    hotspot_cards_bytes,
    hotspot_cards_count,
    hotspot_cards_length,
    hotspot_cards_prefix,
    hotspot_cards_profile_selected,
    hotspot_cards_skip_bytes,
    hotspot_cards_skip_prefix,
    hotspot_cards_skip_uptime,
    hotspot_cards_skip_uptime_type,
    hotspot_cards_start,
    hotspot_cards_type_selected,
    hotspot_cards_uptime_type,
    hotspot_cards_uptime_value,
    hs_back_to_length,
    hs_back_to_profile,
    hs_back_to_type,
    hs_back_to_uptime,
)
from core.card_models import CardData, CardSystem

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _patch_router(monkeypatch):
    """Patch router_selector and clear rate-limit for all tests."""
    router_lookup = lambda uid: (
        "discovered_1" if uid == ADMIN_ID else None
    )  # noqa: E731
    monkeypatch.setattr("bot.router_selector.get_selected_router", router_lookup)
    monkeypatch.setattr("bot.handlers.hotspot_cards.get_selected_router", router_lookup)
    monkeypatch.setattr(
        "bot.router_selector.set_selected_router", lambda uid, key: None
    )
    monkeypatch.setattr(
        "bot.router_selector.set_current_action", lambda uid, action, data=None: None
    )
    monkeypatch.setattr("bot.router_selector.clear_action", lambda uid: None)
    monkeypatch.setattr("bot.router_selector.clear_router", lambda uid: None)
    from utils.admin_decorator import _rate_limit_data

    _rate_limit_data.clear()


def _fake_cards(count: int = 3) -> list[CardData]:
    return [
        CardData(username=f"u{i}", password="p", card_number=i, profile="default")
        for i in range(count)
    ]


# ─── Helper tests ─────────────────────────────────────────────


class TestGetCardTypeKeyboard:
    def test_returns_keyboard(self):
        kb = get_card_type_keyboard()
        assert kb is not None
        # Should have 4 rows
        assert len(kb.inline_keyboard) == 4


# ─── hotspot_cards_start tests ────────────────────────────────


class TestHotspotCardsStart:
    @pytest.mark.asyncio
    async def test_start_with_callback(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hotspot_cards")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_cards.nav_set"):
            result = await hotspot_cards_start(u, c)
        assert result == WAITING_HOTSPOT_CARD_COUNT
        u.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_message(self):
        u = make_mock_update(user_id=ADMIN_ID, text="/cards")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_cards.nav_set"):
            result = await hotspot_cards_start(u, c)
        assert result == WAITING_HOTSPOT_CARD_COUNT


# ─── hotspot_cards_count tests ────────────────────────────────


class TestHotspotCardsCount:
    @pytest.mark.asyncio
    async def test_valid_count(self):
        u = make_mock_update(user_id=ADMIN_ID, text="5")
        c = make_mock_context()
        result = await hotspot_cards_count(u, c)
        assert result == WAITING_HOTSPOT_CARD_LENGTH
        assert c.user_data["hs_card_count"] == 5

    @pytest.mark.asyncio
    async def test_invalid_count_zero(self):
        u = make_mock_update(user_id=ADMIN_ID, text="0")
        c = make_mock_context()
        result = await hotspot_cards_count(u, c)
        assert result == WAITING_HOTSPOT_CARD_COUNT

    @pytest.mark.asyncio
    async def test_invalid_count_text(self):
        u = make_mock_update(user_id=ADMIN_ID, text="abc")
        c = make_mock_context()
        result = await hotspot_cards_count(u, c)
        assert result == WAITING_HOTSPOT_CARD_COUNT


# ─── hotspot_cards_length tests ───────────────────────────────


class TestHotspotCardsLength:
    @pytest.mark.asyncio
    async def test_valid_length(self):
        u = make_mock_update(user_id=ADMIN_ID, text="6")
        c = make_mock_context()
        result = await hotspot_cards_length(u, c)
        assert result == WAITING_HOTSPOT_CARD_PREFIX
        assert c.user_data["hs_card_length"] == 6

    @pytest.mark.asyncio
    async def test_invalid_length(self):
        u = make_mock_update(user_id=ADMIN_ID, text="0")
        c = make_mock_context()
        result = await hotspot_cards_length(u, c)
        assert result == WAITING_HOTSPOT_CARD_LENGTH


# ─── hotspot_cards_prefix tests ───────────────────────────────


class TestHotspotCardsPrefix:
    @pytest.mark.asyncio
    async def test_set_prefix(self):
        u = make_mock_update(user_id=ADMIN_ID, text="guest_")
        c = make_mock_context()
        result = await hotspot_cards_prefix(u, c)
        assert result == WAITING_HOTSPOT_CARD_TYPE
        assert c.user_data["hs_card_prefix"] == "guest_"


# ─── hotspot_cards_skip_prefix tests ──────────────────────────


class TestHotspotCardsSkipPrefix:
    @pytest.mark.asyncio
    async def test_skip(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_prefix")
        c = make_mock_context()
        result = await hotspot_cards_skip_prefix(u, c)
        assert result == WAITING_HOTSPOT_CARD_TYPE
        assert c.user_data["hs_card_prefix"] == ""


# ─── hotspot_cards_type_selected tests ────────────────────────


class TestHotspotCardsTypeSelected:
    @pytest.mark.asyncio
    async def test_type1_different(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_type1")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[{"name": "default"}]),
        ):
            result = await hotspot_cards_type_selected(u, c)
        assert result == WAITING_HOTSPOT_CARD_PROFILE
        assert c.user_data["hs_card_system"] == CardSystem.DIFFERENT_CREDENTIALS

    @pytest.mark.asyncio
    async def test_type2_same(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_type2")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[{"name": "default"}]),
        ):
            await hotspot_cards_type_selected(u, c)
        assert c.user_data["hs_card_system"] == CardSystem.SAME_CREDENTIALS

    @pytest.mark.asyncio
    async def test_type3_empty(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_type3")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[{"name": "default"}]),
        ):
            await hotspot_cards_type_selected(u, c)
        assert c.user_data["hs_card_system"] == CardSystem.EMPTY_PASSWORD

    @pytest.mark.asyncio
    async def test_unknown_type_stays(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_typeX")
        c = make_mock_context()
        result = await hotspot_cards_type_selected(u, c)
        assert result == WAITING_HOTSPOT_CARD_TYPE

    @pytest.mark.asyncio
    async def test_profiles_failure_ends(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_type1")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(side_effect=Exception("net err")),
        ):
            with patch("bot.handlers.hotspot_cards.send_error", new=AsyncMock()):
                result = await hotspot_cards_type_selected(u, c)
        assert result == ConversationHandler.END


# ─── hotspot_cards_profile_selected tests ─────────────────────


class TestHotspotCardsProfileSelected:
    @pytest.mark.asyncio
    async def test_valid_profile(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_profile_premium")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.resolve_profile_from_callback",
            return_value="premium",
        ):
            result = await hotspot_cards_profile_selected(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME
        assert c.user_data["hs_card_profile"] == "premium"

    @pytest.mark.asyncio
    async def test_invalid_profile_ends(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_card_profile_X")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.resolve_profile_from_callback",
            return_value=None,
        ):
            result = await hotspot_cards_profile_selected(u, c)
        assert result == ConversationHandler.END


# ─── Uptime type tests ────────────────────────────────────────


class TestHotspotCardsUptimeType:
    @pytest.mark.asyncio
    async def test_select_hours(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_hours")
        c = make_mock_context()
        result = await hotspot_cards_uptime_type(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME
        assert c.user_data["hs_uptime_unit"] == "hours"

    @pytest.mark.asyncio
    async def test_select_days(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_days")
        c = make_mock_context()
        result = await hotspot_cards_uptime_type(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME
        assert c.user_data["hs_uptime_unit"] == "days"

    @pytest.mark.asyncio
    async def test_unknown_stays(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="uptime_X")
        c = make_mock_context()
        result = await hotspot_cards_uptime_type(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME

    @pytest.mark.asyncio
    async def test_skip_uptime_type(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_uptime")
        c = make_mock_context()
        result = await hotspot_cards_skip_uptime_type(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME
        assert c.user_data["hs_card_uptime"] == ""


# ─── Uptime value tests ───────────────────────────────────────


class TestHotspotCardsUptimeValue:
    @pytest.mark.asyncio
    async def test_valid_value(self):
        u = make_mock_update(user_id=ADMIN_ID, text="5")
        c = make_mock_context()
        c.user_data["hs_uptime_unit"] = "hours"
        result = await hotspot_cards_uptime_value(u, c)
        assert result == WAITING_HOTSPOT_CARD_BYTES
        assert c.user_data["hs_card_uptime"] == "05:00:00"

    @pytest.mark.asyncio
    async def test_invalid_value(self):
        u = make_mock_update(user_id=ADMIN_ID, text="xyz")
        c = make_mock_context()
        c.user_data["hs_uptime_unit"] = "hours"
        result = await hotspot_cards_uptime_value(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME


# ─── Skip uptime tests ────────────────────────────────────────


class TestHotspotCardsSkipUptime:
    @pytest.mark.asyncio
    async def test_skip(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_uptime")
        c = make_mock_context()
        result = await hotspot_cards_skip_uptime(u, c)
        assert result == WAITING_HOTSPOT_CARD_BYTES
        assert c.user_data["hs_card_uptime"] == ""


# ─── Bytes tests ──────────────────────────────────────────────


class TestHotspotCardsBytes:
    @pytest.mark.asyncio
    async def test_valid_bytes_creates_cards(self, tmp_path):
        u = make_mock_update(user_id=ADMIN_ID, text="1G")
        c = make_mock_context()
        c.user_data.update(
            {
                "hs_card_count": 2,
                "hs_card_length": 5,
                "hs_card_prefix": "",
                "hs_card_system": CardSystem.DIFFERENT_CREDENTIALS,
                "hs_card_profile": "default",
                "hs_card_uptime": "",
            }
        )
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(side_effect=[_fake_cards(2), "fake/path.pdf"]),
        ):
            with patch("os.path.exists", return_value=True):
                with patch("os.remove"):
                    with patch("builtins.open", MagicMock()):
                        with patch(
                            "bot.handlers.hotspot_cards.reply_final", new=AsyncMock()
                        ):
                            result = await hotspot_cards_bytes(u, c)
        # Conversation ends; user_data cleaned up
        assert result == ConversationHandler.END
        assert "hs_card_bytes" not in c.user_data

    @pytest.mark.asyncio
    async def test_invalid_bytes_reprompts(self):
        u = make_mock_update(user_id=ADMIN_ID, text="garbage!")
        c = make_mock_context()
        result = await hotspot_cards_bytes(u, c)
        assert result == WAITING_HOTSPOT_CARD_BYTES
        assert "hs_card_bytes" not in c.user_data


# ─── Skip bytes tests ─────────────────────────────────────────


class TestHotspotCardsSkipBytes:
    @pytest.mark.asyncio
    async def test_skip_creates_cards(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_bytes")
        c = make_mock_context()
        c.user_data.update(
            {
                "hs_card_count": 1,
                "hs_card_length": 3,
                "hs_card_prefix": "",
                "hs_card_system": CardSystem.SAME_CREDENTIALS,
                "hs_card_profile": "default",
                "hs_card_uptime": "",
            }
        )
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(side_effect=[_fake_cards(1), "fake/path.pdf"]),
        ):
            with patch("os.path.exists", return_value=True):
                with patch("os.remove"):
                    with patch("builtins.open", MagicMock()):
                        with patch(
                            "bot.handlers.hotspot_cards.reply_final", new=AsyncMock()
                        ):
                            result = await hotspot_cards_skip_bytes(u, c)
        # Conversation ends; user_data cleaned up
        assert result == ConversationHandler.END
        assert "hs_card_bytes" not in c.user_data


# ─── _create_cards tests ──────────────────────────────────────


class TestCreateCards:
    @pytest.mark.asyncio
    async def test_no_router_ends(self, monkeypatch):
        monkeypatch.setattr("bot.router_selector.get_selected_router", lambda uid: None)
        monkeypatch.setattr(
            "bot.handlers.hotspot_cards.get_selected_router", lambda uid: None
        )
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_bytes")
        c = make_mock_context()
        with patch("bot.handlers.hotspot_cards.reply_final", new=AsyncMock()):
            result = await _create_cards(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_cards_ends(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_bytes")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[]),
        ):
            result = await _create_cards(u, c, query=u.callback_query)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception_cleanup(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_skip_bytes")
        c = make_mock_context()
        c.user_data["hs_card_count"] = 1
        with patch(
            "bot.handlers.hotspot_cards.run_blocking",
            new=AsyncMock(side_effect=Exception("router crashed")),
        ):
            with patch(
                "bot.handlers.hotspot_cards.send_error", new=AsyncMock()
            ) as mock_err:
                result = await _create_cards(u, c, query=u.callback_query)
        # Exception is caught and conversation still ends
        assert result == ConversationHandler.END
        mock_err.assert_called_once()


# ─── Back navigation tests ────────────────────────────────────


class TestBackNavigation:
    @pytest.mark.asyncio
    async def test_back_to_length(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_back_to_length")
        c = make_mock_context()
        result = await hs_back_to_length(u, c)
        assert result == WAITING_HOTSPOT_CARD_LENGTH

    @pytest.mark.asyncio
    async def test_back_to_type(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_back_to_type")
        c = make_mock_context()
        result = await hs_back_to_type(u, c)
        assert result == WAITING_HOTSPOT_CARD_TYPE

    @pytest.mark.asyncio
    async def test_back_to_profile_success(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_back_to_profile")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[{"name": "default"}]),
        ):
            result = await hs_back_to_profile(u, c)
        assert result == WAITING_HOTSPOT_CARD_PROFILE

    @pytest.mark.asyncio
    async def test_back_to_profile_failure(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_back_to_profile")
        c = make_mock_context()
        with patch(
            "bot.handlers.hotspot_cards.fetch_and_cache_profiles",
            new=AsyncMock(side_effect=Exception("err")),
        ):
            with patch("bot.handlers.hotspot_cards.send_error", new=AsyncMock()):
                result = await hs_back_to_profile(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_back_to_uptime(self):
        u = make_mock_update(user_id=ADMIN_ID, callback_data="hs_back_to_uptime")
        c = make_mock_context()
        result = await hs_back_to_uptime(u, c)
        assert result == WAITING_HOTSPOT_CARD_UPTIME
