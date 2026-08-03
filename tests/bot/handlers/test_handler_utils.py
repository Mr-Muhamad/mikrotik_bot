"""Tests for bot/handlers/handler_utils.py - shared callback helpers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator  # noqa: I001

P = "bot.handlers.handler_utils"


def _start_patches():
    stack = ExitStack()
    stack.enter_context(
        patch("utils.admin_decorator.ADMIN_IDS", [724730774])
    )
    stack.enter_context(
        patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
    )
    return stack


@pytest.fixture(autouse=True)
def _all_patches():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestGetUserId:
    def test_returns_user_id(self):
        from bot.handlers.handler_utils import get_user_id

        update = make_mock_update(user_id=123)
        assert get_user_id(update) == 123

    def test_returns_none_when_user_missing(self):
        from bot.handlers.handler_utils import get_user_id

        update = make_mock_update()
        update.effective_user = None
        assert get_user_id(update) is None


class TestGetCallbackData:
    def test_returns_data(self):
        from bot.handlers.handler_utils import get_callback_data

        update = make_mock_update(callback_data="some_action")
        assert get_callback_data(update) == "some_action"

    def test_returns_none_when_no_query(self):
        from bot.handlers.handler_utils import get_callback_data

        update = make_mock_update()
        assert get_callback_data(update) is None


class TestGetMessageText:
    def test_returns_text(self):
        from bot.handlers.handler_utils import get_message_text

        update = make_mock_update(text="hello")
        update.effective_message = update.message
        assert get_message_text(update) == "hello"

    def test_returns_none_when_no_message(self):
        from bot.handlers.handler_utils import get_message_text

        update = make_mock_update(callback_data="x")
        update.effective_message = None
        assert get_message_text(update) is None


class TestGetEffectiveMessage:
    def test_returns_message(self):
        from bot.handlers.handler_utils import get_effective_message

        update = make_mock_update(text="hi")
        msg = get_effective_message(update)
        assert msg is not None

    def test_returns_none_for_callback(self):
        from bot.handlers.handler_utils import get_effective_message

        update = make_mock_update(callback_data="x")
        update.effective_message = None
        assert get_effective_message(update) is None


class TestGetQueryMessage:
    def test_returns_cast_message(self):
        from bot.handlers.handler_utils import get_query_message

        update = make_mock_update(callback_data="x")
        result = get_query_message(update.callback_query)
        assert result is not None

    def test_returns_none_when_query_none(self):
        from bot.handlers.handler_utils import get_query_message

        assert get_query_message(None) is None

    def test_returns_none_when_message_none(self):
        from bot.handlers.handler_utils import get_query_message

        q = MagicMock()
        q.message = None
        assert get_query_message(q) is None


class TestGetQueryChatId:
    def test_returns_chat_id(self):
        from bot.handlers.handler_utils import get_query_chat_id

        update = make_mock_update(callback_data="x")
        update.callback_query.message.chat_id = 724730774
        assert get_query_chat_id(update.callback_query) == 724730774

    def test_returns_none_when_query_none(self):
        from bot.handlers.handler_utils import get_query_chat_id

        assert get_query_chat_id(None) is None


class TestAckCallback:
    @pytest.mark.asyncio
    async def test_answers_callback(self):
        from bot.handlers.handler_utils import ack_callback

        update = make_mock_update(callback_data="test")
        query = await ack_callback(update)
        assert query is not None
        import bot.handlers.handler_utils as mod

        mod.safe_answer_callback.assert_awaited_once()  # type: ignore[reportFunctionMemberAccess]

    @pytest.mark.asyncio
    async def test_returns_none_for_message(self):
        from bot.handlers.handler_utils import ack_callback

        update = make_mock_update()
        result = await ack_callback(update)
        assert result is None


class TestParseRouterId:
    @pytest.mark.asyncio
    async def test_extracts_id(self):
        from bot.handlers.handler_utils import parse_router_id

        update = make_mock_update(callback_data="saved_router_42")
        result = await parse_router_id(
            update.callback_query, "saved_router_"
        )
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_none_for_query_none(self):
        from bot.handlers.handler_utils import parse_router_id

        assert await parse_router_id(None, "prefix_") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_data(self):
        from bot.handlers.handler_utils import parse_router_id

        update = make_mock_update(callback_data="prefix_bad")
        result = await parse_router_id(update.callback_query, "prefix_")
        assert result is None
        update.callback_query.edit_message_text.assert_awaited_once()


class TestMakeBackStep:
    @pytest.mark.asyncio
    async def test_returns_next_state(self):
        from bot.handlers.handler_utils import make_back_step

        fake_kb = MagicMock()
        back_fn = make_back_step("msg", lambda: fake_kb, 5)
        update = make_mock_update(callback_data="back")
        ctx = MagicMock()
        result = await back_fn(update, ctx)
        assert result == 5
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_edit_with_keyboard(self):
        from bot.handlers.handler_utils import make_back_step

        fake_kb = MagicMock()
        back_fn = make_back_step("prompt", lambda: fake_kb, 3)
        update = make_mock_update(callback_data="go_back")
        ctx = MagicMock()
        await back_fn(update, ctx)
        update.callback_query.edit_message_text.assert_awaited_once_with(
            "prompt", reply_markup=fake_kb
        )
