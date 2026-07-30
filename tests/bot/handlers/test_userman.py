"""Tests for bot.handlers.userman."""

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import (
    WAITING_CARD_COUNT,
    WAITING_CARD_MAC,
    WAITING_CARD_PAYMENT,
    WAITING_CARD_PREFIX,
    WAITING_CARD_PROFILE,
    WAITING_CARD_TIMESTAMP,
    WAITING_CARD_TYPE,
)
from bot.handlers.userman import (
    userman_card_count,
    userman_card_mac_selected,
    userman_card_payment_selected,
    userman_card_profile_selected,
    userman_card_type_selected,
    userman_cards_start,
    userman_list,
    userman_profiles,
)
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


@pytest.fixture(autouse=True)
def _mock_db_session():
    """Mock the DB session lookups and router selection."""
    with (
        patch("bot.router_selector.get_user_session", return_value={}),
        patch("bot.router_selector.save_user_session"),
        patch("bot.router_selector.get_selected_router", return_value="discovered_1"),
        patch("bot.handlers.userman.get_selected_router", return_value="discovered_1"),
    ):
        yield


def _ctx(user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot = MagicMock()
    return ctx


def _query_update(callback_data=None):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = callback_data
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


class TestUsermanCardsStart:
    @pytest.mark.asyncio
    async def test_start_shows_card_types(self):
        with patch("bot.handlers.userman.edit_clean", new=AsyncMock()):
            result = await userman_cards_start(_query_update("userman_cards"), _ctx())
        assert result == WAITING_CARD_TYPE


class TestUsermanCardTypeSelected:
    @pytest.mark.asyncio
    async def test_with_profiles_advances_to_profile(self):
        with patch(
            "bot.handlers.userman.fetch_and_cache_profiles",
            new=AsyncMock(return_value=["1M", "2M"]),
        ):
            result = await userman_card_type_selected(_query_update("card_type1"), _ctx())
        assert result == WAITING_CARD_PROFILE

    @pytest.mark.asyncio
    async def test_with_dict_profiles_extracts_name(self):
        with patch(
            "bot.handlers.userman.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[{"name": "1M"}, {"name": "2M"}]),
        ):
            ctx = _ctx()
            result = await userman_card_type_selected(_query_update("card_type1"), ctx)
        assert result == WAITING_CARD_PROFILE

    @pytest.mark.asyncio
    async def test_no_profiles_ends(self):
        with patch(
            "bot.handlers.userman.fetch_and_cache_profiles",
            new=AsyncMock(return_value=[]),
        ):
            result = await userman_card_type_selected(_query_update("card_type1"), _ctx())
        assert result == ConversationHandler.END


class TestUsermanCardProfileSelected:
    @pytest.mark.asyncio
    async def test_valid_profile_advances_to_payment(self):
        ctx = _ctx()
        ctx.user_data["profile_names"] = ["1M", "2M"]
        with patch("bot.handlers.userman.resolve_profile_from_callback", return_value="1M"):
            result = await userman_card_profile_selected(_query_update("card_profile_0"), ctx)
        assert result == WAITING_CARD_PAYMENT
        assert ctx.user_data["card_profile"] == "1M"

    @pytest.mark.asyncio
    async def test_invalid_profile_ends(self):
        with patch("bot.handlers.userman.resolve_profile_from_callback", return_value=None):
            result = await userman_card_profile_selected(_query_update("card_profile_x"), _ctx())
        assert result == ConversationHandler.END


class TestUsermanCardPaymentSelected:
    @pytest.mark.asyncio
    async def test_paid_advances_to_timestamp_step(self):
        # بعد اختيار طريقة الدفع، تنتقل المحادثة إلى خطوة الطابع الزمني (TIMESTAMP)
        # وليس مباشرة إلى MAC — تم إضافة خطوة الطابع الزمني بعد كتابة هذا الاختبار.
        ctx = _ctx()
        result = await userman_card_payment_selected(_query_update("card_paid"), ctx)
        assert result == WAITING_CARD_TIMESTAMP
        assert ctx.user_data["card_payment"] == "مدفوع"

    @pytest.mark.asyncio
    async def test_unpaid_advances_to_timestamp_step(self):
        # نفس السبب: خطوة TIMESTAMP أُضيفت بين PAYMENT و MAC في تدفق الإنشاء.
        ctx = _ctx()
        result = await userman_card_payment_selected(_query_update("card_unpaid"), ctx)
        assert result == WAITING_CARD_TIMESTAMP
        assert ctx.user_data["card_payment"] == "غير مدفوع"


class TestUsermanCardCount:
    @pytest.mark.asyncio
    async def test_invalid_count_reprompts(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(id=1)
        update.message = MagicMock()
        update.message.text = "abc"

        with (
            patch(
                "bot.handlers.userman.validate_positive_int",
                return_value=(False, "Invalid"),
            ),
            patch("bot.handlers.userman.send_step", new=AsyncMock()),
        ):
            result = await userman_card_count(update, _ctx())
        assert result == WAITING_CARD_COUNT

    @pytest.mark.asyncio
    async def test_count_too_high_reprompts(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(id=1)
        update.message = MagicMock()
        update.message.text = "501"

        with (
            patch("bot.handlers.userman.validate_positive_int", return_value=(True, "")),
            patch("bot.handlers.userman.send_step", new=AsyncMock()),
        ):
            result = await userman_card_count(update, _ctx())
        assert result == WAITING_CARD_COUNT

    @pytest.mark.asyncio
    async def test_success_sends_text_and_pdf(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(id=1)
        update.message = MagicMock()
        update.message.text = "3"

        ctx = _ctx({"card_type": "type1", "card_profile": "1M"})
        status = MagicMock()
        status.message_id = 999

        cards = [
            {"username": "111", "password": "222"},
            {"username": "333", "password": "444"},
        ]

        with (
            patch("bot.handlers.userman.validate_positive_int", return_value=(True, "")),
            patch("bot.handlers.userman.send_step", new=AsyncMock(return_value=status)),
            patch(
                "bot.handlers.userman.run_blocking",
                new=AsyncMock(side_effect=[cards, None, "/tmp/cards.pdf", None]),
            ),
            patch("bot.handlers.userman.userman_manager") as mock_um,
            patch("bot.handlers.userman.card_generator") as mock_cg,
            patch("bot.handlers.userman.log_action"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch("builtins.open", mock_open(read_data=b"PDF")),
        ):
            mock_um.create_cards = MagicMock(return_value=cards)
            mock_um.format_card = MagicMock(
                side_effect=lambda c, i: f"Card#{i + 1}: {c['username']}"
            )
            mock_cg.generate_pdf = MagicMock(return_value="/tmp/cards.pdf")
            ctx.bot.delete_message = AsyncMock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot.send_document = AsyncMock()

            result = await userman_card_count(update, ctx)

        assert result == ConversationHandler.END
        assert ctx.bot.send_message.call_count >= 1
        assert ctx.bot.send_document.call_count == 1

    @pytest.mark.asyncio
    async def test_exception_ends(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(id=1)
        update.message = MagicMock()
        update.message.text = "3"

        ctx = _ctx({"card_type": "type1", "card_profile": "1M"})

        with (
            patch("bot.handlers.userman.validate_positive_int", return_value=(True, "")),
            patch("bot.handlers.userman.send_step", new=AsyncMock(return_value=None)),
            patch(
                "bot.handlers.userman.run_blocking",
                new=AsyncMock(side_effect=OSError("net down")),
            ),
            patch("bot.handlers.userman.send_error", new=AsyncMock()),
        ):
            result = await userman_card_count(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_sends_secret_free_confirmation(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(id=1)
        update.message = MagicMock()
        update.message.text = "15"

        ctx = _ctx({"card_type": "type1", "card_profile": "1M"})
        status = MagicMock()
        status.message_id = 999

        cards = [{"username": f"u{i}", "password": f"p{i}"} for i in range(15)]

        with (
            patch("bot.handlers.userman.validate_positive_int", return_value=(True, "")),
            patch("bot.handlers.userman.send_step", new=AsyncMock(return_value=status)),
            patch(
                "bot.handlers.userman.run_blocking",
                new=AsyncMock(side_effect=[cards, None, "/tmp/x.pdf", None]),
            ),
            patch("bot.handlers.userman.userman_manager") as mock_um,
            patch("bot.handlers.userman.card_generator"),
            patch("bot.handlers.userman.log_action"),
            patch("os.path.exists", return_value=False),
        ):
            mock_um.create_cards = MagicMock(return_value=cards)
            ctx.bot.delete_message = AsyncMock()
            ctx.bot.send_message = AsyncMock()

            await userman_card_count(update, ctx)

        text = ctx.bot.send_message.call_args.kwargs["text"]
        # رسالة تأكيد خالية من بيانات الدخول (يوزر/باسورد) — الملف PDF هو المخرج الرسمي.
        assert "تم إنشاء 15 كارت بنجاح" in text
        assert "p0" not in text and "u0" not in text


class TestUsermanList:
    @pytest.mark.asyncio
    async def test_list_with_users(self):
        update = _query_update("userman_list")
        ctx = _ctx({"router_key": "discovered_1"})
        users = [{"name": "u1"}, {"name": "u2"}]

        with (
            patch("bot.handlers.userman.run_blocking", new=AsyncMock(return_value=users)),
            patch("bot.handlers.userman.format_user_list", return_value="U1\nU2"),
        ):
            await userman_list(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        args = update.callback_query.edit_message_text.call_args
        assert "U1" in args.args[0]

    @pytest.mark.asyncio
    async def test_list_exception(self):
        update = _query_update("userman_list")
        ctx = _ctx({"router_key": "discovered_1"})

        with patch(
            "bot.handlers.userman.run_blocking",
            new=AsyncMock(side_effect=OSError("boom")),
        ):
            await userman_list(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
        text = call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "❌" in text


class TestUsermanProfiles:
    @pytest.mark.asyncio
    async def test_profiles_with_data(self):
        update = _query_update("userman_profiles")
        ctx = _ctx({"router_key": "discovered_1"})

        with patch(
            "bot.handlers.userman.run_blocking",
            new=AsyncMock(return_value=["1M", "2M"]),
        ):
            await userman_profiles(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "1M" in text
        assert "2M" in text

    @pytest.mark.asyncio
    async def test_profiles_empty(self):
        update = _query_update("userman_profiles")
        ctx = _ctx({"router_key": "discovered_1"})

        with patch("bot.handlers.userman.run_blocking", new=AsyncMock(return_value=[])):
            await userman_profiles(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "❌" in text or "لا توجد" in text

    @pytest.mark.asyncio
    async def test_profiles_exception(self):
        update = _query_update("userman_profiles")
        ctx = _ctx({"router_key": "discovered_1"})

        with patch(
            "bot.handlers.userman.run_blocking",
            new=AsyncMock(side_effect=OSError("net down")),
        ):
            await userman_profiles(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
        text = call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "❌" in text


class TestUsermanCardMacSelected:
    @pytest.mark.asyncio
    async def test_bind_known_returns_mac_state(self):
        ctx = _ctx()
        result = await userman_card_mac_selected(_query_update("card_bind_known"), ctx)
        assert result == WAITING_CARD_PREFIX

    @pytest.mark.asyncio
    async def test_no_bind_returns_count_state(self):
        ctx = _ctx()
        result = await userman_card_mac_selected(_query_update("card_no_bind"), ctx)
        assert result == WAITING_CARD_PREFIX
        assert ctx.user_data.get("card_caller_id") == ""
        assert ctx.user_data.get("card_caller_id") == ""
