"""Tests for admin_decorator — require_role, _is_group_chat, _get_rate_limit."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import ADMIN_IDS
from utils.admin_decorator import (
    INSUFFICIENT_ROLE_MSG,
    _get_rate_limit,
    _is_group_chat,
    _rate_limit_data,
    require_role,
    reset_rate_limit,
)


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    _rate_limit_data.clear()
    yield
    _rate_limit_data.clear()


def _update(user_id=100, has_message=True, has_callback=False, chat_type="private"):
    u = MagicMock()
    u.effective_user = MagicMock(id=user_id)
    u.message = MagicMock() if has_message else None
    if u.message:
        u.message.reply_text = AsyncMock()
    u.callback_query = MagicMock() if has_callback else None
    if u.callback_query:
        u.callback_query.answer = AsyncMock()
        u.callback_query.edit_message_text = AsyncMock()
    u.effective_chat = MagicMock()
    u.effective_chat.type = chat_type
    return u


# ─── _get_rate_limit ──────────────────────────────────────────


class TestGetRateLimit:
    def test_reboot_returns_10(self):
        assert _get_rate_limit("do_reboot") == 10.0

    def test_backup_returns_30(self):
        assert _get_rate_limit("start_backup") == 30.0

    def test_restore_returns_60(self):
        assert _get_rate_limit("do_restore") == 60.0

    def test_delete_returns_5(self):
        assert _get_rate_limit("delete_user") == 5.0

    def test_add_returns_2(self):
        assert _get_rate_limit("add_user") == 2.0

    def test_edit_returns_2(self):
        assert _get_rate_limit("edit_user") == 2.0

    def test_unknown_returns_default(self):
        assert _get_rate_limit("some_random_func") == 1.0


# ─── reset_rate_limit ────────────────────────────────────────


class TestResetRateLimit:
    def test_clears_user_entries(self):
        _rate_limit_data[(100, "handler")] = 1.0
        _rate_limit_data[(100, "other")] = 2.0
        _rate_limit_data[(200, "handler")] = 3.0
        reset_rate_limit(100)
        assert (100, "handler") not in _rate_limit_data
        assert (100, "other") not in _rate_limit_data
        assert (200, "handler") in _rate_limit_data


# ─── _is_group_chat ───────────────────────────────────────────


class TestIsGroupChat:
    def test_private_chat(self):
        u = _update(chat_type="private")
        assert _is_group_chat(u) is False

    def test_group_chat(self):
        u = _update(chat_type="group")
        assert _is_group_chat(u) is True

    def test_supergroup_chat(self):
        u = _update(chat_type="supergroup")
        assert _is_group_chat(u) is True

    def test_no_chat(self):
        u = MagicMock()
        u.effective_chat = None
        assert _is_group_chat(u) is False


# ─── require_role ─────────────────────────────────────────────


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_super_admin_passes_admin_requirement(self):
        admin_id = next(iter(ADMIN_IDS))

        @require_role("admin")
        async def handler(update, context):
            return "ok"

        u = _update(user_id=admin_id)
        result = await handler(u, MagicMock())
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_group_chat_returns_none(self):
        @require_role("viewer")
        async def handler(update, context):
            return "ok"

        u = _update(chat_type="group")
        result = await handler(u, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_user_returns_none(self):
        @require_role("viewer")
        async def handler(update, context):
            return "ok"

        u = MagicMock()
        u.effective_user = None
        result = await handler(u, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_unauthorized_user_blocked(self):
        @require_role("viewer")
        async def handler(update, context):
            return "ok"

        u = _update(user_id=999999)
        with patch("database.models.get_admin_role", return_value=None):
            result = await handler(u, MagicMock())
        assert result is None
        u.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_insufficient_role_blocked(self):
        @require_role("admin")
        async def handler(update, context):
            return "ok"

        u = _update(user_id=999999)
        with patch("database.models.get_admin_role", return_value="viewer"):
            result = await handler(u, MagicMock())
        assert result is None
        u.message.reply_text.assert_called_once_with(INSUFFICIENT_ROLE_MSG)

    @pytest.mark.asyncio
    async def test_sufficient_role_passes(self):
        @require_role("operator")
        async def handler(update, context):
            return "ok"

        u = _update(user_id=999999)
        with patch("database.models.get_admin_role", return_value="admin"):
            result = await handler(u, MagicMock())
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_no_role_defaults_to_admin(self):
        @require_role("admin")
        async def handler(update, context):
            return "ok"

        u = _update(user_id=999999)
        with patch("database.models.get_admin_role", return_value=None):
            # user_id not in ADMIN_IDS and no db_role → blocked
            result = await handler(u, MagicMock())
        assert result is None
