"""Tests for utils.tg_helpers — assertion failures and all helper functions."""

from unittest.mock import MagicMock

import pytest

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


def _mock_context(user_data=None):  # type: ignore[reportMissingParameterType]
    ctx = MagicMock()
    ctx.user_data = user_data
    return ctx


def _mock_update(text="hello", user_id=1, chat_id=1, message_id=10):  # type: ignore[reportMissingParameterType]
    u = MagicMock()
    u.message = MagicMock()
    u.message.text = text
    u.message.chat_id = chat_id
    u.message.message_id = message_id
    u.effective_user = MagicMock(id=user_id)
    u.effective_chat = MagicMock(id=chat_id)
    return u


# ─── get_user_data ────────────────────────────────────────────


class TestGetUserData:
    def test_returns_user_data(self):
        ctx = _mock_context(user_data={"key": "value"})
        assert get_user_data(ctx) == {"key": "value"}

    def test_asserts_on_none(self):
        ctx = _mock_context(user_data=None)
        with pytest.raises(AssertionError):
            get_user_data(ctx)


# ─── get_query_data ───────────────────────────────────────────


class TestGetQueryData:
    def test_returns_data(self):
        q = MagicMock()
        q.data = "some_callback"
        assert get_query_data(q) == "some_callback"

    def test_asserts_on_none(self):
        q = MagicMock()
        q.data = None
        with pytest.raises(AssertionError):
            get_query_data(q)


# ─── get_message_text ─────────────────────────────────────────


class TestGetMessageText:
    def test_returns_stripped_text(self):
        u = _mock_update(text="  hello  ")
        assert get_message_text(u) == "hello"

    def test_asserts_on_no_message(self):
        u = MagicMock()
        u.message = None
        with pytest.raises(AssertionError):
            get_message_text(u)

    def test_asserts_on_no_text(self):
        u = MagicMock()
        u.message = MagicMock()
        u.message.text = None
        with pytest.raises(AssertionError):
            get_message_text(u)


# ─── get_message ──────────────────────────────────────────────


class TestGetMessage:
    def test_returns_message(self):
        u = _mock_update()
        assert get_message(u) is u.message

    def test_asserts_on_none(self):
        u = MagicMock()
        u.message = None
        with pytest.raises(AssertionError):
            get_message(u)


# ─── get_effective_user_id ────────────────────────────────────


class TestGetEffectiveUserId:
    def test_returns_id(self):
        u = _mock_update(user_id=42)
        assert get_effective_user_id(u) == 42

    def test_asserts_on_none(self):
        u = MagicMock()
        u.effective_user = None
        with pytest.raises(AssertionError):
            get_effective_user_id(u)


# ─── get_chat_id ──────────────────────────────────────────────


class TestGetChatIdHelper:
    def test_returns_id(self):
        u = _mock_update(chat_id=55)
        assert get_chat_id(u) == 55

    def test_asserts_on_none(self):
        u = MagicMock()
        u.effective_chat = None
        with pytest.raises(AssertionError):
            get_chat_id(u)


# ─── get_from_user_id ────────────────────────────────────────


class TestGetFromUserId:
    def test_returns_id(self):
        q = MagicMock()
        q.from_user = MagicMock(id=77)
        assert get_from_user_id(q) == 77

    def test_asserts_on_none(self):
        q = MagicMock()
        q.from_user = None
        with pytest.raises(AssertionError):
            get_from_user_id(q)


# ─── get_query_message ────────────────────────────────────────


class TestGetQueryMessage:
    def test_returns_message(self):
        q = MagicMock()
        q.message = MagicMock()
        assert get_query_message(q) is q.message

    def test_none_query(self):
        assert get_query_message(None) is None

    def test_none_message(self):
        q = MagicMock()
        q.message = None
        assert get_query_message(q) is None


# ─── get_query_chat_id ───────────────────────────────────────


class TestGetQueryChatIdHelper:
    def test_returns_chat_id(self):
        q = MagicMock()
        q.message = MagicMock()
        q.message.chat_id = 88
        assert get_query_chat_id(q) == 88

    def test_none_query(self):
        assert get_query_chat_id(None) is None

    def test_none_message(self):
        q = MagicMock()
        q.message = None
        assert get_query_chat_id(q) is None
