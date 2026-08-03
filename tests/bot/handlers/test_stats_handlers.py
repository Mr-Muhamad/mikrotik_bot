"""Tests for bot.handlers.stats."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import stats as stats_module
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _mock_deps():  # type: ignore[reportUnusedFunction]
    """Replace stats_hotspot/stats_userman with direct function references.

    Since @admin_only/@require_router wrap the original functions at import time,
    we replace the module-level names with the original _show_stats function
    so the tests can drive the handlers directly.
    """
    original_show_stats = stats_module._show_stats  # type: ignore[reportPrivateUsage]

    async def stats_hotspot_direct(update, context):  # type: ignore[reportMissingParameterType]
        return await original_show_stats(update, context, "hotspot")

    async def stats_userman_direct(update, context):  # type: ignore[reportMissingParameterType]
        return await original_show_stats(update, context, "userman")

    # Mutate module dict directly so the new references survive decorator wrapping
    saved_hotspot = stats_module.stats_hotspot
    saved_userman = stats_module.stats_userman

    stats_module.stats_hotspot = stats_hotspot_direct
    stats_module.stats_userman = stats_userman_direct

    with (
        patch("bot.router_selector.get_user_session", return_value={}),
        patch("bot.router_selector.save_user_session"),
    ):
        try:
            yield
        finally:
            stats_module.stats_hotspot = saved_hotspot
            stats_module.stats_userman = saved_userman
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


def _query_update():
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


class TestStatsHotspot:
    @pytest.mark.asyncio
    async def test_hotspot_stats_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        stats = {
            "total_users": 5,
            "active_users": 3,
            "inactive_users": 2,
            "total_bytes": 1000,
        }

        # run_blocking يُستدعى 4 مرات: router_name, get_hotspot_stats, get_yesterday_snapshot, get_week_snapshots  # noqa: E501
        with (
            patch(
                "bot.handlers.stats.run_blocking",
                new=AsyncMock(side_effect=["Router1", stats, None, []]),
            ),
            patch("bot.handlers.stats.stats_manager") as mock_sm,
        ):
            mock_sm.format_hotspot_stats.return_value = "📊 Stats: 5 users"
            mock_sm.format_vs_yesterday.return_value = ""
            mock_sm.format_trend_chart.return_value = ""
            await stats_module.stats_hotspot(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "5 users" in text

    @pytest.mark.asyncio
    async def test_hotspot_stats_error(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with (
            patch(
                "bot.handlers.stats.run_blocking",
                new=AsyncMock(side_effect=["Router1", ConnectionError("net down")]),
            ),
            patch("bot.handlers.stats.stats_manager") as mock_sm,
        ):
            mock_sm.format_hotspot_stats.return_value = ""
            await stats_module.stats_hotspot(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
        text = call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "❌" in text


class TestStatsUserman:
    @pytest.mark.asyncio
    async def test_userman_stats_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        stats = {"total_users": 10, "enabled_users": 7, "disabled_users": 3}

        with (
            patch(
                "bot.handlers.stats.run_blocking",
                new=AsyncMock(side_effect=["Router1", stats]),
            ),
            patch("bot.handlers.stats.stats_manager") as mock_sm,
        ):
            mock_sm.format_userman_stats.return_value = "📊 UserMan: 10 cards"
            await stats_module.stats_userman(update, ctx)
        text = update.callback_query.edit_message_text.call_args.args[0]
        assert "10 cards" in text

    @pytest.mark.asyncio
    async def test_userman_stats_error(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        with (
            patch(
                "bot.handlers.stats.run_blocking",
                new=AsyncMock(side_effect=["Router1", ConnectionError("timeout")]),
            ),
            patch("bot.handlers.stats.stats_manager") as mock_sm,
        ):
            mock_sm.format_userman_stats.return_value = ""
            await stats_module.stats_userman(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
        text = call_kwargs.get("text", "")
        assert "discovered_1" in text
        assert "⏱" in text

    @pytest.mark.asyncio
    async def test_stats_chart_callback_success(self):
        ctx = MagicMock()
        ctx.bot.send_photo = AsyncMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        mock_chart_mod = MagicMock()
        mock_chart_mod.generate_trend_chart = AsyncMock(
            return_value=b"\x89PNGfakechartbytes"
        )
        with (
            patch.dict(
                sys.modules, {"core.chart_generator": mock_chart_mod}
            ),
            patch(
                "bot.handlers.stats.run_blocking",
                new=AsyncMock(side_effect=[[], "Router1", b"\x89PNGfakechartbytes"]),
            ),
        ):
            await stats_module.stats_chart_callback(update, ctx)
        ctx.bot.send_photo.assert_called_once()
        kwargs = ctx.bot.send_photo.call_args.kwargs
        assert kwargs["photo"] == b"\x89PNGfakechartbytes"
