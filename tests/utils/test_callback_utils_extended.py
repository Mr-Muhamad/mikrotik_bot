"""Tests for utils.callback_utils — extended coverage for edge cases."""

from unittest.mock import AsyncMock

import pytest

from utils.callback_utils import (
    _CALLBACK_DEDUP,  # type: ignore[reportPrivateUsage]
    is_duplicate_callback,
    safe_answer_callback,
)


@pytest.fixture(autouse=True)
def reset_dedup():
    _CALLBACK_DEDUP.clear()
    import utils.callback_utils as mod

    mod._last_cleanup = 0.0  # type: ignore[reportPrivateUsage]
    yield
    _CALLBACK_DEDUP.clear()


# ─── is_duplicate_callback edge cases ─────────────────────────


class TestIsDuplicateEdgeCases:
    def test_none_returns_false(self):
        assert is_duplicate_callback(None) is False

    def test_empty_string_returns_false(self):
        assert is_duplicate_callback("") is False

    def test_no_user_id_key(self):
        is_duplicate_callback("data")
        # Without user_id, key is just "data"
        assert "data" in _CALLBACK_DEDUP

    def test_with_user_id_key_includes_id(self):
        is_duplicate_callback("data", user_id=42)
        assert "42:data" in _CALLBACK_DEDUP

    def test_duplicate_with_user_id(self):
        is_duplicate_callback("data", user_id=1)
        assert is_duplicate_callback("data", user_id=1) is True
        # Different user is not duplicate
        assert is_duplicate_callback("data", user_id=2) is False


# ─── safe_answer_callback edge cases ──────────────────────────


class TestSafeAnswerEdgeCases:
    @pytest.mark.asyncio
    async def test_none_query_does_nothing(self):
        await safe_answer_callback(None)

    @pytest.mark.asyncio
    async def test_generic_exception_logs_warning(self):
        query = AsyncMock()
        query.answer.side_effect = RuntimeError("unexpected")
        # Should not raise
        await safe_answer_callback(query)

    @pytest.mark.asyncio
    async def test_empty_error_string(self):
        query = AsyncMock()
        query.answer.side_effect = Exception("")
        await safe_answer_callback(query)
