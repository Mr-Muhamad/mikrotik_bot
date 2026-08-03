from unittest.mock import MagicMock

import pytest

from tests.fixtures.telegram_mocks import CallbackQueryMock, make_mock_update
from utils.tg_helpers import (
    get_chat_id,
    get_effective_user_id,
    get_from_user_id,
    get_message,
    get_message_text,
    get_query_chat_id,
    get_query_data,
    get_query_message,
    get_user_data,
)


class TestGetUserData:
    def test_returns_user_data(self):
        ctx = MagicMock()
        ctx.user_data = {"key": "val"}
        assert get_user_data(ctx) == {"key": "val"}

    def test_raises_on_none(self):
        ctx = MagicMock()
        ctx.user_data = None
        with pytest.raises(AssertionError):
            get_user_data(ctx)


class TestGetQueryData:
    def test_returns_data_string(self):
        q = CallbackQueryMock(data="action:123")
        assert get_query_data(q) == "action:123"  # type: ignore[reportArgumentType]

    def test_raises_on_none(self):
        q = MagicMock()
        q.data = None
        with pytest.raises(AssertionError):
            get_query_data(q)


class TestGetMessageText:
    def test_returns_stripped_text(self):
        update = make_mock_update(text="  hello  ")
        assert get_message_text(update) == "hello"

    def test_raises_on_none_message(self):
        update = make_mock_update()
        update.message = None
        with pytest.raises(AssertionError):
            get_message_text(update)

    def test_raises_on_none_text(self):
        update = make_mock_update()
        update.message.text = None
        with pytest.raises(AssertionError):
            get_message_text(update)


class TestGetMessage:
    def test_returns_message_object(self):
        update = make_mock_update(text="test")
        msg = get_message(update)
        assert msg.text == "test"

    def test_raises_on_none(self):
        update = make_mock_update()
        update.message = None
        with pytest.raises(AssertionError):
            get_message(update)


class TestGetEffectiveUserId:
    def test_returns_user_id(self):
        update = make_mock_update(user_id=123)
        assert get_effective_user_id(update) == 123

    def test_raises_on_none(self):
        update = make_mock_update()
        update.effective_user = None
        with pytest.raises(AssertionError):
            get_effective_user_id(update)


class TestGetChatId:
    def test_returns_chat_id(self):
        update = make_mock_update(chat_id=456)
        assert get_chat_id(update) == 456

    def test_raises_on_none(self):
        update = make_mock_update()
        update.effective_chat = None
        with pytest.raises(AssertionError):
            get_chat_id(update)


class TestGetFromUserId:
    def test_returns_from_user_id(self):
        q = CallbackQueryMock(from_user_id=789)
        assert get_from_user_id(q) == 789  # type: ignore[reportArgumentType]

    def test_raises_on_none(self):
        q = MagicMock()
        q.from_user = None
        with pytest.raises(AssertionError):
            get_from_user_id(q)


class TestGetQueryMessage:
    def test_returns_message(self):
        q = CallbackQueryMock()
        msg = get_query_message(q)  # type: ignore[reportArgumentType]
        assert msg is q.message

    def test_returns_none_for_none_query(self):
        assert get_query_message(None) is None

    def test_returns_none_for_none_message(self):
        q = MagicMock()
        q.message = None
        assert get_query_message(q) is None


class TestGetQueryChatId:
    def test_returns_chat_id(self):
        q = CallbackQueryMock()
        assert get_query_chat_id(q) == q.message.chat_id  # type: ignore[reportArgumentType]

    def test_returns_none_for_none_query(self):
        assert get_query_chat_id(None) is None

    def test_returns_none_for_none_message(self):
        q = MagicMock()
        q.message = None
        assert get_query_chat_id(q) is None
