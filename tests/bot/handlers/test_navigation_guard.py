"""Tests for the centralized navigation guard (string-based classification)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.callback_constants import PATTERNS
from bot.router_selector import (
    ROUTER_MGMT_COMMANDS,
    ROUTER_MGMT_PATTERN_NAMES,
    navigation_guard,
    requires_router_check,
)


@pytest.mark.asyncio
async def test_requires_router_check_command_management_exempt():
    for cmd in ROUTER_MGMT_COMMANDS:
        assert requires_router_check(cmd, None) is False


@pytest.mark.asyncio
async def test_requires_router_check_command_operational_guarded():
    assert requires_router_check("hotspot", None) is True
    assert requires_router_check("backup", None) is True


@pytest.mark.asyncio
async def test_requires_router_check_pattern_management_exempt():
    for name in ROUTER_MGMT_PATTERN_NAMES:
        assert requires_router_check(None, PATTERNS[name]) is False


@pytest.mark.asyncio
async def test_requires_router_check_pattern_operational_guarded():
    assert requires_router_check(None, PATTERNS["menu_hotspot"]) is True
    assert requires_router_check(None, PATTERNS["hotspot_add"]) is True
    assert requires_router_check(None, PATTERNS["host_kick_execute"]) is True


@pytest.mark.asyncio
async def test_navigation_guard_blocks_without_router():
    called = AsyncMock()

    @navigation_guard
    async def handler(update, context):
        called()

    update = MagicMock()
    update.effective_user = MagicMock(id=999)
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.message = None

    ctx = MagicMock()
    ctx.user_data = {}

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "bot.router_selector.get_selected_router",
            lambda uid: None,
        )
        mp.setattr(
            "bot.router_selector.get_router_keyboard",
            lambda: "KEYBOARD",
        )
        await handler(update, ctx)

    called.assert_not_awaited()
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_navigation_guard_allows_with_router():
    ran = []

    @navigation_guard
    async def handler(update, context):
        ran.append(True)

    update = MagicMock()
    update.effective_user = MagicMock(id=999)
    update.callback_query = None
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update.message = msg

    ctx = MagicMock()
    ctx.user_data = {}

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "bot.router_selector.get_selected_router",
            lambda uid: "discovered_1",
        )
        mp.setattr(
            "bot.router_selector._fast_reachability_check",
            AsyncMock(return_value=True),
        )
        await handler(update, ctx)

    assert ran == [True]
    msg.reply_text.assert_not_awaited()
