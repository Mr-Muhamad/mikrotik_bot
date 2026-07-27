"""Tests for bot/handlers/hotspot_delete.py — all handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from bot.handlers.constants import WAITING_DELETE_ID, WAITING_INPUT
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.hotspot_delete"


async def _call_through(fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(
        f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through
    ))
    stack.enter_context(patch(f"{P}.send_error", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.is_duplicate_callback", return_value=False))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.set_current_action"))
    stack.enter_context(patch(f"{P}.edit_clean", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.delete_now", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.log_action"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestHotspotDeleteStart:
    @pytest.mark.asyncio
    async def test_callback_path(self):
        update = make_mock_update(user_id=724730774, callback_data="delete")
        context = make_mock_context()
        from bot.handlers.hotspot_delete import hotspot_delete_start

        result = await hotspot_delete_start(update, context)
        assert result == WAITING_DELETE_ID

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = make_mock_update(user_id=724730774, text="/delete")
        context = make_mock_context()
        from bot.handlers.hotspot_delete import hotspot_delete_start

        result = await hotspot_delete_start(update, context)
        assert result == WAITING_DELETE_ID


class TestHotspotDeleteSelect:
    @pytest.mark.asyncio
    async def test_user_found_shows_confirm(self):
        update = make_mock_update(user_id=724730774, callback_data="delete_user_*1")
        context = make_mock_context()
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value={"name": "testuser", "profile": "default"},
        ):
            from bot.handlers.hotspot_delete import hotspot_delete_select

            result = await hotspot_delete_select(update, context)
        assert result == WAITING_INPUT
        assert context.user_data["delete_user_id"] == "*1"

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        update = make_mock_update(user_id=724730774, callback_data="delete_user_999")
        context = make_mock_context()
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from bot.handlers.hotspot_delete import hotspot_delete_select

            result = await hotspot_delete_select(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_exception_sends_error(self):
        update = make_mock_update(user_id=724730774, callback_data="delete_user_1")
        context = make_mock_context()
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            side_effect=OSError("API error"),
        ):
            from bot.handlers.hotspot_delete import hotspot_delete_select

            result = await hotspot_delete_select(update, context)
        assert result == -1


class TestConfirmCallback:
    @pytest.mark.asyncio
    async def test_duplicate_returns_none(self):
        update = make_mock_update(user_id=724730774, callback_data="confirm_yes")
        context = make_mock_context()
        with patch(f"{P}.is_duplicate_callback", return_value=True):
            from bot.handlers.hotspot_delete import confirm_callback

            result = await confirm_callback(update, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_confirm_yes_success(self):
        update = make_mock_update(user_id=724730774, callback_data="confirm_yes")
        context = make_mock_context()
        context.user_data["delete_user_id"] = "*1"
        from bot.handlers.hotspot_delete import confirm_callback

        result = await confirm_callback(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_confirm_yes_incomplete_data(self):
        update = make_mock_update(user_id=724730774, callback_data="confirm_yes")
        context = make_mock_context()
        with patch(f"{P}.get_selected_router", return_value=None):
            from bot.handlers.hotspot_delete import confirm_callback

            result = await confirm_callback(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_confirm_no(self):
        update = make_mock_update(user_id=724730774, callback_data="confirm_no")
        context = make_mock_context()
        context.user_data["delete_user_id"] = "*1"
        from bot.handlers.hotspot_delete import confirm_callback

        result = await confirm_callback(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_confirm_yes_delete_fails(self):
        update = make_mock_update(user_id=724730774, callback_data="confirm_yes")
        context = make_mock_context()
        context.user_data["delete_user_id"] = "*1"
        with patch(
            f"{P}.hotspot_manager.delete_user",
            new_callable=AsyncMock,
            side_effect=OSError("Delete failed"),
        ):
            from bot.handlers.hotspot_delete import confirm_callback

            result = await confirm_callback(update, context)
        assert result == -1


class TestConfirmReprompt:
    @pytest.mark.asyncio
    async def test_deletes_message_and_returns_input(self):
        update = make_mock_update(user_id=724730774, text="some text")
        context = make_mock_context()
        from bot.handlers.hotspot_delete import confirm_reprompt

        result = await confirm_reprompt(update, context)
        assert result == WAITING_INPUT
