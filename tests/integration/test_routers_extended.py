"""Tests for router discovery entry, rename, and credential flows."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.routers import (
    disc_enter_password,
    disc_enter_username,
    discovered_router_selected,
    rename_router_start,
    rename_router_value,
)
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_disc_limiter_clear()


def admin_disc_limiter_clear():
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _seed_router(ip="10.0.0.1", identity="SeedRouter", version="7.10"):  # type: ignore[reportMissingParameterType]
    from database.models import save_discovered_router

    return save_discovered_router(
        ip=ip,
        username="",
        password="",
        identity=identity,
        version=version,
        last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


class TestDiscoveredRouterSelected:
    @pytest.mark.asyncio
    async def test_known_router_prompts_username(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.handlers.constants import WAITING_DISC_USERNAME

        rid = _seed_router()
        update = make_mock_update(callback_data="disc_router_10.0.0.1")
        context = _make_context()
        context.user_data = {}

        with patch(
            "bot.handlers.router_flows.discovery.get_router_by_ip",
            return_value={"id": rid},
        ):
            result = await discovered_router_selected(update, context)
        assert result == WAITING_DISC_USERNAME
        assert context.user_data["disc_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_unknown_router_ip_prompts_for_credentials(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.handlers.constants import WAITING_DISC_USERNAME

        update = make_mock_update(callback_data="disc_router_99.99.99.99")
        context = _make_context()

        with patch("bot.handlers.router_flows.discovery.get_router_by_ip", return_value=None):
            result = await discovered_router_selected(update, context)
        assert result == WAITING_DISC_USERNAME


class TestDiscEnterUsername:
    @pytest.mark.asyncio
    async def test_saves_username(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.handlers.constants import WAITING_DISC_PASSWORD

        update = make_mock_update(text="admin")
        context = _make_context()
        context.user_data["disc_ip"] = "10.0.0.1"

        result = await disc_enter_username(update, context)
        assert result == WAITING_DISC_PASSWORD
        assert context.user_data["disc_username"] == "admin"


class TestDiscEnterPassword:
    @pytest.mark.asyncio
    async def test_password_success_connects(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.router_selector import get_selected_router

        update = make_mock_update(text="secret")
        context = _make_context()
        context.user_data["disc_ip"] = "10.0.0.1"
        context.user_data["disc_username"] = "admin"

        status_msg = MagicMock()
        status_msg.message_id = 100
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        async def fake_run_blocking(func, *args, **kwargs):  # type: ignore[reportMissingParameterType]
            skip_names = {
                "get_router_by_ip",
                "check_router_health",
                "detect_router_system",
            }
            if getattr(func, "__name__", "") in skip_names:
                return None
            result = func(*args, **kwargs)
            if hasattr(result, "__await__"):
                return await result
            return result

        with (
            patch("bot.handlers.router_flows.discovery.mikrotik_api") as mock_api,
            patch(
                "bot.handlers.router_flows.discovery.run_blocking",
                new=AsyncMock(side_effect=fake_run_blocking),
            ),
            patch("bot.handlers.router_flows.discovery.schedule_delete", new=AsyncMock()),
        ):
            mock_api.test_connection = AsyncMock(return_value=(True, "7.10", "MyRouter"))
            result = await disc_enter_password(update, context)
        assert result == ConversationHandler.END
        assert get_selected_router(ADMIN_ID) is not None

    @pytest.mark.asyncio
    async def test_password_failure_ends(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="wrongpass")
        context = _make_context()
        context.user_data["disc_ip"] = "10.0.0.1"
        context.user_data["disc_username"] = "admin"
        status_msg = MagicMock()
        status_msg.message_id = 100
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        with (
            patch("bot.handlers.router_flows.discovery.mikrotik_api"),
            patch(
                "bot.handlers.router_flows.discovery.run_blocking",
                new=AsyncMock(return_value=(False, "auth fail", "")),
            ),
            patch("bot.handlers.router_flows.discovery.schedule_delete", new=AsyncMock()),
            patch("bot.handlers.router_flows.discovery.get_router_by_ip", return_value=None),
        ):
            result = await disc_enter_password(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_password_exception_ends(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="x")
        context = _make_context()
        context.user_data["disc_ip"] = "10.0.0.1"
        context.user_data["disc_username"] = "admin"
        status_msg = MagicMock()
        status_msg.message_id = 100
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        with (
            patch("bot.handlers.router_flows.discovery.mikrotik_api"),
            patch(
                "bot.handlers.router_flows.discovery.run_blocking",
                new=AsyncMock(side_effect=Exception("net down")),
            ),
            patch("bot.handlers.router_flows.discovery.send_error", new=AsyncMock()) as mock_err,
            patch("bot.handlers.router_flows.discovery.schedule_delete", new=AsyncMock()),
            patch("bot.handlers.router_flows.discovery.get_router_by_ip", return_value=None),
        ):
            result = await disc_enter_password(update, context)
        assert result == ConversationHandler.END
        mock_err.assert_called_once()


class TestRenameRouter:
    @pytest.mark.asyncio
    async def test_rename_start_prompts_for_name(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.handlers.constants import WAITING_RENAME

        rid = _seed_router()
        update = make_mock_update(callback_data=f"rename_router_{rid}")
        context = _make_context()

        result = await rename_router_start(update, context)
        assert result == WAITING_RENAME
        assert context.user_data["rename_router_id"] == rid

    @pytest.mark.asyncio
    async def test_rename_value_updates_alias(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from database.models import get_router_by_id

        rid = _seed_router(ip="10.0.0.5", identity="OldName")
        assert rid is not None
        update = make_mock_update(text="NewName")
        context = _make_context()
        context.user_data["rename_router_id"] = rid

        with patch("bot.handlers.router_flows.rename.mikrotik_api"):
            result = await rename_router_value(update, context)
        assert result == ConversationHandler.END
        router = get_router_by_id(rid)
        assert router is not None
        assert router["name_alias"] == "NewName"

    @pytest.mark.asyncio
    async def test_rename_value_empty_name_reprompts(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        from bot.handlers.constants import WAITING_RENAME

        rid = _seed_router()
        update = make_mock_update(text="   ")
        context = _make_context()
        context.user_data["rename_router_id"] = rid

        result = await rename_router_value(update, context)
        assert result == WAITING_RENAME

    @pytest.mark.asyncio
    async def test_rename_value_no_id_ends(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        update = make_mock_update(text="x")
        context = _make_context()
        result = await rename_router_value(update, context)
        assert result == ConversationHandler.END
