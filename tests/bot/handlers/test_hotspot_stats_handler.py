"""Tests for bot.handlers.hotspot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import hotspot as hotspot_module
from utils import admin_decorator

ADMIN_ID = 724730774


def _direct_hotspot_stats(update, context):
    """Direct invocation bypassing @admin_only decorator."""
    original = getattr(hotspot_module, "_original_hotspot_stats", None)
    if original is None:
        original = getattr(hotspot_module.hotspot_stats, "__wrapped__")
        setattr(hotspot_module, "_original_hotspot_stats", original)
    return original(update, context)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


@pytest.fixture(autouse=True)
def _bypass_decorators():
    """Replace handlers with the unwrapped functions to bypass decorators.

    The handlers are decorated as @admin_only(original). __wrapped__ from
    @admin_only points to the actual original function.
    """
    if not hasattr(hotspot_module, "_original_hotspot_stats"):
        setattr(
            hotspot_module,
            "_original_hotspot_stats",
            getattr(hotspot_module.hotspot_stats, "__wrapped__"),
        )
    hotspot_module.hotspot_stats = getattr(hotspot_module, "_original_hotspot_stats")
    if not hasattr(hotspot_module, "_original_hotspot_stats_day_input"):
        setattr(
            hotspot_module,
            "_original_hotspot_stats_day_input",
            getattr(hotspot_module.hotspot_stats_day_input, "__wrapped__"),
        )
    hotspot_module.hotspot_stats_day_input = getattr(
        hotspot_module, "_original_hotspot_stats_day_input"
    )
    yield


def _query_update(data="hotspot_stats"):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = data
    update.callback_query = query
    return update


def _message_update(text="5"):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.callback_query = None
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    update.message = message
    return update


def _base_stats(**overrides):
    stats = {
        "total": 100,
        "active": 30,
        "inactive": 70,
        "categories": {
            "10 GB": 10,
            "20 GB": 20,
            "30 GB": 15,
            "40 GB": 5,
            "50 GB": 10,
            "أخرى": 40,
        },
        "resets_by_day": {},
        "reset_days": [],
        "reset_list": [],
        "selected_day": None,
    }
    stats.update(overrides)
    return stats


class TestHotspotStats:
    @pytest.mark.asyncio
    async def test_entry_with_reset_days(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        stats = _base_stats(
            reset_days=[5, 4, 3],
            resets_by_day={
                5: [("PREFIX_2026-07-05", "10 GB")],
                4: [("PREFIX_2026-07-04", "20 GB")],
                3: [("PREFIX_2026-07-03", "30 GB")],
            },
        )

        with patch(
            "bot.handlers.hotspot.run_blocking", new=AsyncMock(return_value=stats)
        ):
            result = await hotspot_module.hotspot_stats(update, ctx)
        assert result == hotspot_module.WAITING_STATS_DAY
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "100" in text
        assert "30" in text
        assert "أدخل رقم اليوم" in text
        assert "5, 4, 3" in text

    @pytest.mark.asyncio
    async def test_entry_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with patch(
            "bot.handlers.hotspot.run_blocking",
            new=AsyncMock(side_effect=Exception("net down")),
        ):
            result = await hotspot_module.hotspot_stats(update, ctx)
        assert result is None
        update.callback_query.edit_message_text.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
        text = call_kwargs.get("text", "")
        assert "❌" in text
        assert "discovered_1" in text

    @pytest.mark.asyncio
    async def test_entry_no_reset_days(self):
        from telegram.ext import ConversationHandler

        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with patch(
            "bot.handlers.hotspot.run_blocking",
            new=AsyncMock(return_value=_base_stats()),
        ):
            result = await hotspot_module.hotspot_stats(update, ctx)
        assert result == ConversationHandler.END
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "لا توجد سجلات تصفير" in text


class TestHotspotStatsDayInput:
    @pytest.mark.asyncio
    async def test_day_view(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _message_update("5")

        stats = _base_stats(
            selected_day=5,
            reset_days=[5, 4, 3],
            resets_by_day={
                5: [("PREFIX_2026-07-05", "10 GB")],
                4: [("PREFIX_2026-07-04", "20 GB")],
            },
            reset_list=[("PREFIX_2026-07-05", "10 GB")],
        )

        with patch(
            "bot.handlers.hotspot.run_blocking", new=AsyncMock(return_value=stats)
        ):
            result = await hotspot_module.hotspot_stats_day_input(update, ctx)
        assert result == hotspot_module.WAITING_STATS_DAY
        text = update.message.reply_text.call_args.args[0]
        assert "يوم (5)" in text
        assert "PREFIX_2026-07-05" in text

    @pytest.mark.asyncio
    async def test_non_numeric(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _message_update("abc")

        with patch(
            "bot.handlers.hotspot.run_blocking",
            new=AsyncMock(return_value=_base_stats()),
        ):
            result = await hotspot_module.hotspot_stats_day_input(update, ctx)
        assert result == hotspot_module.WAITING_STATS_DAY
        text = update.message.reply_text.call_args.args[0]
        assert "يرجى إدخال رقم يوم صحيح" in text

    @pytest.mark.asyncio
    async def test_out_of_range(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _message_update("32")

        with patch(
            "bot.handlers.hotspot.run_blocking",
            new=AsyncMock(return_value=_base_stats()),
        ):
            result = await hotspot_module.hotspot_stats_day_input(update, ctx)
        assert result == hotspot_module.WAITING_STATS_DAY
        text = update.message.reply_text.call_args.args[0]
        assert "يرجى إدخال رقم يوم صحيح" in text

    @pytest.mark.asyncio
    async def test_day_not_found(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _message_update("9")

        stats = _base_stats(
            reset_days=[5, 4, 3],
            resets_by_day={
                5: [("PREFIX_2026-07-05", "10 GB")],
            },
            reset_list=[],
            selected_day=None,
        )
        with patch(
            "bot.handlers.hotspot.run_blocking", new=AsyncMock(return_value=stats)
        ):
            result = await hotspot_module.hotspot_stats_day_input(update, ctx)
        assert result == hotspot_module.WAITING_STATS_DAY
        text = update.message.reply_text.call_args.args[0]
        assert "لا توجد سجلات تصفير لليوم 9" in text
        assert "5, 4, 3" in text
