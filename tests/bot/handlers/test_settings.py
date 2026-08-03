"""Tests for bot.handlers.settings."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_PDF_VALUE
from bot.handlers.settings import pdf_settings_option, pdf_settings_value
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _mock_db():  # type: ignore[reportUnusedFunction]
    with (
        patch("bot.router_selector.get_user_session", return_value={}),
        patch("bot.router_selector.save_user_session"),
    ):
        yield


def _query_update(callback_data):  # type: ignore[reportMissingParameterType]
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = callback_data
    query.from_user = MagicMock(id=ADMIN_ID)
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


def _text_update(text):  # type: ignore[reportMissingParameterType]
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.message = MagicMock()
    update.message.text = text
    return update


def _ctx(user_data=None):  # type: ignore[reportMissingParameterType]
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


class TestPdfSettingsOption:
    @pytest.mark.asyncio
    async def test_margins_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {
                "margin_top": 10,
                "margin_bottom": 10,
                "margin_left": 10,
                "margin_right": 10,
            }
            ctx = _ctx()
            update = _query_update("pdf_margins")
            result = await pdf_settings_option(update, ctx)
        assert result == WAITING_PDF_VALUE
        assert ctx.user_data["pdf_option"] == "margins"

    @pytest.mark.asyncio
    async def test_spacing_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"spacing_x": 5, "spacing_y": 5}
            result = await pdf_settings_option(_query_update("pdf_spacing"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_cards_per_row_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"cards_per_row": 4}
            result = await pdf_settings_option(_query_update("pdf_cards_per_row"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_cards_per_page_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"cards_per_page": 40}
            result = await pdf_settings_option(_query_update("pdf_cards_per_page"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_brand_name_option_empty(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"brand_name": ""}
            result = await pdf_settings_option(_query_update("pdf_brand_name"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_hotspot_dns_option_empty(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"hotspot_dns": ""}
            result = await pdf_settings_option(_query_update("pdf_hotspot_dns"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_show_qr_option_enabled(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"show_qr": 1}
            result = await pdf_settings_option(_query_update("pdf_show_qr"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_show_qr_option_disabled(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"show_qr": 0}
            result = await pdf_settings_option(_query_update("pdf_show_qr"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_footer_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {"footer_text": ""}
            result = await pdf_settings_option(_query_update("pdf_footer"), _ctx())
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_unknown_option(self):
        with patch("bot.handlers.settings.pdf_settings") as mock_ps:
            mock_ps.get_settings.return_value = {}
            update = _query_update("pdf_unknown")
            result = await pdf_settings_option(update, _ctx())
        assert result == WAITING_PDF_VALUE
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "❌" in text or "غير معروف" in text


class TestPdfSettingsValue:
    @pytest.mark.asyncio
    async def test_margins_valid(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "margins"})
            update = _text_update("10 20 30 40")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(
            margin_top=10, margin_bottom=20, margin_left=30, margin_right=40
        )

    @pytest.mark.asyncio
    async def test_margins_invalid_count_reprompts(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.send_step", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "margins"})
            update = _text_update("10 20 30")
            result = await pdf_settings_value(update, ctx)
        assert result == WAITING_PDF_VALUE
        mock_ps.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_spacing_valid(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "spacing"})
            update = _text_update("5 10")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(spacing_x=5, spacing_y=10)

    @pytest.mark.asyncio
    async def test_spacing_invalid_count_reprompts(self):
        with patch("bot.handlers.settings.send_step", new=AsyncMock()):
            ctx = _ctx({"pdf_option": "spacing"})
            update = _text_update("5")
            result = await pdf_settings_value(update, ctx)
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_cards_per_row(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "cards_per_row"})
            update = _text_update("5")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(cards_per_row=5)

    @pytest.mark.asyncio
    async def test_cards_per_page(self):
        with patch("bot.handlers.settings.reply_final", new=AsyncMock()):
            ctx = _ctx({"pdf_option": "cards_per_page"})
            update = _text_update("60")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_brand_name(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "brand_name"})
            update = _text_update("MyBrand")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(brand_name="MyBrand")

    @pytest.mark.asyncio
    async def test_hotspot_dns(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "hotspot_dns"})
            update = _text_update("login.local")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(hotspot_dns="login.local")

    @pytest.mark.asyncio
    async def test_show_qr_enabled(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "show_qr"})
            update = _text_update("1")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(show_qr=1)

    @pytest.mark.asyncio
    async def test_show_qr_disabled(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "show_qr"})
            update = _text_update("0")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(show_qr=0)

    @pytest.mark.asyncio
    async def test_footer(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
        ):
            ctx = _ctx({"pdf_option": "footer"})
            update = _text_update("MyFooter")
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
        mock_ps.update.assert_called_once_with(footer_text="MyFooter")

    @pytest.mark.asyncio
    async def test_invalid_value_exception_ends(self):
        with (
            patch("bot.handlers.settings.pdf_settings") as mock_ps,
            patch("bot.handlers.settings.reply_final", new=AsyncMock()),
            patch("bot.handlers.settings.send_error", new=AsyncMock()),
        ):
            mock_ps.update.side_effect = ValueError("DB error")
            ctx = _ctx({"pdf_option": "cards_per_row"})
            update = _text_update("not_a_number")
            result = await pdf_settings_value(update, ctx)
        assert result == WAITING_PDF_VALUE

    @pytest.mark.asyncio
    async def test_no_option_ends(self):
        ctx = _ctx({})
        update = _text_update("anything")
        with patch("bot.handlers.settings.reply_final", new=AsyncMock()):
            result = await pdf_settings_value(update, ctx)
        assert result == ConversationHandler.END
