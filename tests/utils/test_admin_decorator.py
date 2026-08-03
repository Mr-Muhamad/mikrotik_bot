"""Tests for utils.admin_decorator — admin gating and rate limiting."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.router_selector import require_router
from config import ADMIN_IDS
from utils.admin_decorator import (
    ADMIN_ONLY_MSG,
    NOT_OWNER_MSG,
    RATE_LIMIT_WINDOW,
    _check_rate_limit,  # type: ignore[reportPrivateUsage]
    _rate_limit_data,  # type: ignore[reportPrivateUsage]
    admin_only,
    require_ownership,
)


def _update(user_id: int = 100, has_message: bool = True, has_callback: bool = False):
    u = MagicMock()
    u.effective_user = MagicMock(id=user_id)
    u.message = MagicMock() if has_message else None
    if u.message:
        u.message.reply_text = AsyncMock()
    u.callback_query = MagicMock() if has_callback else None
    if u.callback_query:
        u.callback_query.answer = AsyncMock()
        u.callback_query.edit_message_text = AsyncMock()
    return u


def _ctx():
    c = MagicMock()
    c.user_data = {}
    return c


@pytest.fixture(autouse=True)
def _clear_rate_limit():  # type: ignore[reportUnusedFunction]
    """Reset rate limit cache between tests."""
    _rate_limit_data.clear()
    _rate_limit_data["_test_enforce_rate_limit"] = True
    yield
    _rate_limit_data.clear()


# ─── admin_only tests ──────────────────────────────────────────


class TestAdminOnlyAllowsAdmin:
    @pytest.mark.asyncio
    async def test_admin_passes_through(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        admin_id = next(iter(ADMIN_IDS))
        update = _update(user_id=admin_id)
        ctx = _ctx()
        result = await handler(update, ctx)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_admin_with_message_is_blocked(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        update = _update(user_id=999999)
        ctx = _ctx()
        result = await handler(update, ctx)
        assert result is None
        update.message.reply_text.assert_called_once_with(ADMIN_ONLY_MSG)

    @pytest.mark.asyncio
    async def test_non_admin_with_callback_is_blocked(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        update = _update(user_id=999999, has_message=False, has_callback=True)
        ctx = _ctx()
        result = await handler(update, ctx)
        assert result is None
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(ADMIN_ONLY_MSG)


class TestAdminOnlyRateLimit:
    @pytest.mark.asyncio
    async def test_second_call_within_window_is_blocked(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        admin_id = next(iter(ADMIN_IDS))
        u1 = _update(user_id=admin_id)
        u2 = _update(user_id=admin_id)
        ctx = _ctx()
        await handler(u1, ctx)
        # Push timestamp to pass the 50ms guard
        _rate_limit_data[(admin_id, "handler")] = time.monotonic() - 0.1
        result = await handler(u2, ctx)
        # Second call within 1s is dropped
        assert result is None

    @pytest.mark.asyncio
    async def test_call_after_window_succeeds(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        admin_id = next(iter(ADMIN_IDS))
        u1 = _update(user_id=admin_id)
        u2 = _update(user_id=admin_id)
        ctx = _ctx()
        await handler(u1, ctx)
        # Simulate window passing
        _rate_limit_data[(admin_id, "handler")] -= RATE_LIMIT_WINDOW + 0.5
        result = await handler(u2, ctx)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_rate_limited_callback_answers_query(self):
        @admin_only
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        admin_id = next(iter(ADMIN_IDS))
        u1 = _update(user_id=admin_id)
        u2 = _update(user_id=admin_id, has_message=False, has_callback=True)
        ctx = _ctx()
        await handler(u1, ctx)
        # Push timestamp to pass the 50ms guard
        _rate_limit_data[(admin_id, "handler")] = time.monotonic() - 0.1
        await handler(u2, ctx)
        u2.callback_query.answer.assert_called_once()


# ─── _check_rate_limit tests ──────────────────────────────────


class TestCheckRateLimit:
    def test_first_call_returns_true(self):
        assert _check_rate_limit(42) is True

    def test_immediate_second_call_returns_false(self):
        _check_rate_limit(42)
        # Push timestamp to pass the 50ms guard in _check_rate_limit
        _rate_limit_data[(42, "")] = time.monotonic() - 0.1
        assert _check_rate_limit(42) is False

    def test_different_users_independent(self):
        _check_rate_limit(1)
        assert _check_rate_limit(2) is True
        # Push timestamp to pass the 50ms guard
        _rate_limit_data[(1, "")] = time.monotonic() - 0.1
        assert _check_rate_limit(1) is False

    def test_stale_entries_cleaned_after_interval(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        # Force cleanup trigger
        from utils import admin_decorator

        admin_decorator._last_cleanup = 0.0  # type: ignore[reportPrivateUsage]
        # Insert stale entry
        _rate_limit_data[99] = time.monotonic() - 7200  # 2 hours old  # type: ignore[reportArgumentType]
        # New call triggers cleanup
        _check_rate_limit(100)
        assert 99 not in _rate_limit_data


# ─── require_router tests ─────────────────────────────────────


class TestRequireRouter:
    @pytest.mark.asyncio
    async def test_with_router_proceeds(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        from unittest.mock import AsyncMock

        from bot.router_selector import set_selected_router

        admin_id = next(iter(ADMIN_IDS))
        set_selected_router(admin_id, "discovered_1")

        monkeypatch.setattr(
            "bot.router_selector._fast_reachability_check",
            AsyncMock(return_value=True),
        )

        @require_router
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ran"

        u = _update(user_id=admin_id)
        c = _ctx()
        result = await handler(u, c)
        assert result == "ran"
        assert c.user_data["router_key"] == "discovered_1"

    @pytest.mark.asyncio
    async def test_without_router_message_prompts(self):
        @require_router
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ran"

        u = _update(user_id=999999, has_message=True, has_callback=False)
        c = _ctx()
        with patch("bot.router_selector.get_selected_router", return_value=None):
            result = await handler(u, c)
        assert result is None
        u.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_router_callback_shows_keyboard(self):
        @require_router
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ran"

        u = _update(user_id=999999, has_message=False, has_callback=True)
        c = _ctx()
        with patch("bot.router_selector.get_selected_router", return_value=None):
            result = await handler(u, c)
        assert result is None
        u.callback_query.answer.assert_called_once()
        u.callback_query.edit_message_text.assert_called_once()


# ─── require_ownership tests ────────────────────────────────────


class TestRequireOwnership:
    @pytest.mark.asyncio
    async def test_admin_bypasses_ownership_check(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        admin_id = next(iter(ADMIN_IDS))
        u = _update(user_id=admin_id)
        c = _ctx()
        result = await handler(u, c)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_admin_owner_callback_passes(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        with patch("database.repositories.routers.get_router_by_id") as mock_get:
            mock_get.return_value = {"id": 1, "owner_id": 42, "password": ""}
            u = _update(user_id=42, has_message=False, has_callback=True)
            u.callback_query.data = "connect_router_1"
            c = _ctx()
            result = await handler(u, c)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_owner_callback_blocked(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        with patch("database.repositories.routers.get_router_by_id") as mock_get:
            mock_get.return_value = {"id": 1, "owner_id": 42, "password": ""}
            u = _update(user_id=100, has_message=False, has_callback=True)
            u.callback_query.data = "connect_router_1"
            c = _ctx()
            result = await handler(u, c)
            assert result is None
            u.callback_query.answer.assert_called_once()
            u.callback_query.edit_message_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_non_owner_message_blocked(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        with patch("database.repositories.routers.get_router_by_id") as mock_get:
            mock_get.return_value = {"id": 1, "owner_id": 42, "password": ""}
            u = _update(user_id=100, has_message=True, has_callback=False)
            c = _ctx()
            c.user_data["router_key"] = "discovered_1"
            result = await handler(u, c)
            assert result is None
            u.message.reply_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_unresolvable_router_id_rejects_non_superadmin(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        u = _update(user_id=100, has_message=False, has_callback=True)
        u.callback_query.data = "some_other_action"
        c = _ctx()
        result = await handler(u, c)
        assert result is None
        u.callback_query.answer.assert_called_once()
        u.callback_query.edit_message_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_owner_id_zero_rejects_non_superadmin(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        with patch("database.repositories.routers.get_router_by_id") as mock_get:
            mock_get.return_value = {"id": 1, "owner_id": 0, "password": ""}
            u = _update(user_id=100, has_message=False, has_callback=True)
            u.callback_query.data = "connect_router_1"
            c = _ctx()
            result = await handler(u, c)
            assert result is None
            u.callback_query.answer.assert_called_once()
            u.callback_query.edit_message_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_router_not_found_rejects_non_superadmin(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        with patch("database.repositories.routers.get_router_by_id") as mock_get:
            mock_get.return_value = None
            u = _update(user_id=100, has_message=False, has_callback=True)
            u.callback_query.data = "connect_router_1"
            c = _ctx()
            result = await handler(u, c)
            assert result is None
            u.callback_query.answer.assert_called_once()
            u.callback_query.edit_message_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_no_router_id_message_blocked_for_non_superadmin(self):
        @require_ownership
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            return "ok"

        u = _update(user_id=100, has_message=True, has_callback=False)
        c = _ctx()
        result = await handler(u, c)
        assert result is None
        u.message.reply_text.assert_called_once_with(NOT_OWNER_MSG)

    @pytest.mark.asyncio
    async def test_extract_router_id_from_callback_data(self):
        from utils.admin_decorator import _extract_router_id  # type: ignore[reportPrivateUsage]

        u = _update(has_message=False, has_callback=True)
        u.callback_query.data = "connect_router_42"
        c = _ctx()
        assert _extract_router_id(u, c) == 42

    @pytest.mark.asyncio
    async def test_extract_router_id_from_user_data(self):
        from utils.admin_decorator import _extract_router_id  # type: ignore[reportPrivateUsage]

        u = _update(has_message=True, has_callback=False)
        u.message.text = "/somecommand"
        c = _ctx()
        c.user_data["router_key"] = "discovered_7"
        assert _extract_router_id(u, c) == 7
