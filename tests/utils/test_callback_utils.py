"""Tests for utils.callback_utils module."""

import time
from unittest.mock import AsyncMock

import pytest

from utils.callback_utils import (
    _CALLBACK_DEDUP,
    is_duplicate_callback,
    safe_answer_callback,
)


@pytest.fixture(autouse=True)
def reset_dedup():
    """Reset _CALLBACK_DEDUP before each test."""
    _CALLBACK_DEDUP.clear()
    import utils.callback_utils as mod

    mod._last_cleanup = 0.0
    yield
    _CALLBACK_DEDUP.clear()


class TestIsDuplicateCallback:
    def test_first_call_returns_false(self):
        assert is_duplicate_callback("test_data") is False

    def test_immediate_second_call_returns_true(self):
        is_duplicate_callback("test_data")
        assert is_duplicate_callback("test_data") is True

    def test_different_keys_independent(self):
        is_duplicate_callback("key1")
        assert is_duplicate_callback("key1") is True
        assert is_duplicate_callback("key2") is False

    def test_with_user_id_independent(self):
        is_duplicate_callback("data", user_id=1)
        assert is_duplicate_callback("data", user_id=1) is True
        assert is_duplicate_callback("data", user_id=2) is False

    def test_cleanup_removes_old_entries(self):
        # Add old entry manually
        _CALLBACK_DEDUP["old_key"] = time.monotonic() - 120
        _CALLBACK_DEDUP["new_key"] = time.monotonic()

        # Force cleanup by resetting _last_cleanup
        import utils.callback_utils as mod

        mod._last_cleanup = 0.0

        is_duplicate_callback("trigger_cleanup")
        assert "old_key" not in _CALLBACK_DEDUP
        assert "new_key" in _CALLBACK_DEDUP


class TestSafeAnswerCallback:
    @pytest.mark.asyncio
    async def test_calls_answer(self):
        query = AsyncMock()
        await safe_answer_callback(query)
        query.answer.assert_called_once_with(text=None, show_alert=False)

    @pytest.mark.asyncio
    async def test_calls_answer_with_text(self):
        query = AsyncMock()
        await safe_answer_callback(query, text="test", show_alert=True)
        query.answer.assert_called_once_with(text="test", show_alert=True)

    @pytest.mark.asyncio
    async def test_ignores_query_too_old(self):
        query = AsyncMock()
        query.answer.side_effect = Exception("Query is too old")
        # Should not raise
        await safe_answer_callback(query)

    @pytest.mark.asyncio
    async def test_ignores_invalid_query_id(self):
        query = AsyncMock()
        query.answer.side_effect = Exception("query id is invalid")
        # Should not raise
        await safe_answer_callback(query)
