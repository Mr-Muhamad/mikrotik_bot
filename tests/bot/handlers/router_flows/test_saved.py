"""Tests for bot/handlers/router_flows/saved.py - saved router management."""

import sqlite3
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.router_flows.saved"


def _start_patches():
    stack = ExitStack()
    stack.enter_context(
        patch("utils.admin_decorator.ADMIN_IDS", [724730774])
    )
    stack.enter_context(
        patch(f"{P}.ack_callback", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.parse_router_id", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.run_blocking", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.send_error", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.edit_clean", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.log_action", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.set_selected_router")
    )
    stack.enter_context(
        patch(f"{P}.check_router_health", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.reset_rate_limit")
    )
    stack.enter_context(
        patch(f"{P}.update_router_last_seen", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.update_router_identity", new_callable=AsyncMock)
    )
    stack.enter_context(
        patch(f"{P}.mikrotik_api")
    )
    stack.enter_context(
        patch(f"{P}.get_router_display_name", return_value="TestRouter")
    )
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


def _make_router(db_id=1, identity="Router", ip="10.0.0.1",
                 port=8728, username="admin", password="pass",
                 version="7.14", board="hAP"):
    return {
        "id": db_id, "identity": identity, "ip_address": ip,
        "port": port, "username": username, "password": password,
        "version": version, "board": board,
    }


class TestBuildRouterStatusText:
    def test_online_router(self):
        from bot.handlers.router_flows.saved import (
            _build_router_status_text,
        )

        routers = [
            {"identity": "R1", "ip_address": "10.0.0.1",
             "version": "7.14"},
        ]
        text = _build_router_status_text(routers)
        assert "R1" in text
        assert "10.0.0.1" in text

    def test_offline_router(self):
        from bot.handlers.router_flows.saved import (
            _build_router_status_text,
        )

        routers = [
            {"identity": "R1", "ip_address": "10.0.0.1",
             "version": ""},
        ]
        text = _build_router_status_text(routers)
        assert "R1" in text

    def test_empty_list(self):
        from bot.handlers.router_flows.saved import (
            _build_router_status_text,
        )

        text = _build_router_status_text([])
        assert text is not None


class TestSavedRoutersList:
    @pytest.mark.asyncio
    async def test_empty_routers_shows_empty_msg(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.run_blocking.return_value = []
        update = make_mock_update(callback_data="saved_routers")
        ctx = make_mock_context()
        await mod.saved_routers_list(update, ctx)
        mod.ack_callback.assert_awaited_once()
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routers_shows_list(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.run_blocking.return_value = [_make_router()]
        update = make_mock_update(callback_data="saved_routers")
        ctx = make_mock_context()
        await mod.saved_routers_list(update, ctx)
        mod.edit_clean.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_calls_send_error(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.run_blocking.side_effect = sqlite3.Error("db fail")
        update = make_mock_update(callback_data="saved_routers")
        ctx = make_mock_context()
        await mod.saved_routers_list(update, ctx)
        mod.send_error.assert_awaited_once()


class TestConnectRouter:
    @pytest.mark.asyncio
    async def test_no_credentials_shows_error(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        router = _make_router(username="")
        mod.run_blocking.return_value = router
        update = make_mock_update(callback_data="connect_router_1")
        ctx = make_mock_context()
        await mod.connect_router(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited_once()

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        router = _make_router()
        mod.run_blocking.side_effect = [
            router,
            (True, "7.14", "TestRouter"),
            None,
            None,
            None,
            None,
        ]
        update = make_mock_update(callback_data="connect_router_1")
        ctx = make_mock_context()
        await mod.connect_router(update, ctx)
        mod.set_selected_router.assert_called_once()
        mod.edit_clean.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        router = _make_router()
        mod.run_blocking.side_effect = [
            router,
            (False, "auth fail", ""),
        ]
        update = make_mock_update(callback_data="connect_router_1")
        ctx = make_mock_context()
        await mod.connect_router(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited()

    @pytest.mark.asyncio
    async def test_connection_exception(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        router = _make_router()
        mod.run_blocking.side_effect = [router, OSError("net")]
        update = make_mock_update(callback_data="connect_router_1")
        ctx = make_mock_context()
        await mod.connect_router(update, ctx)
        mod.send_error.assert_awaited_once()


class TestDeleteRouterConfirm:
    @pytest.mark.asyncio
    async def test_shows_confirm_dialog(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        router = _make_router()
        mod.run_blocking.return_value = router
        update = make_mock_update(
            callback_data="delete_router_1"
        )
        ctx = make_mock_context()
        await mod.delete_router_confirm(update, ctx)
        mod.edit_clean.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_router_not_found(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        mod.run_blocking.return_value = None
        update = make_mock_update(
            callback_data="delete_router_1"
        )
        ctx = make_mock_context()
        await mod.delete_router_confirm(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited_once()


class TestDeleteRouterExecute:
    @pytest.mark.asyncio
    async def test_confirm_deletes_router(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.parse_router_id.return_value = 1
        mod.run_blocking.return_value = _make_router()
        update = make_mock_update(
            callback_data="confirm_delete_router_yes_1"
        )
        ctx = make_mock_context()
        await mod.delete_router_execute(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_shows_cancelled(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        update = make_mock_update(
            callback_data="confirm_delete_router_no_1"
        )
        ctx = make_mock_context()
        await mod.delete_router_execute(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited_once()


class TestRefreshRouters:
    @pytest.mark.asyncio
    async def test_refresh_shows_status(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.run_blocking.side_effect = [
            [_make_router()],
            (True, "7.14", "R1"),
            None,
            [_make_router()],
        ]
        mod.mikrotik_api.test_connection.return_value = (
            True, "7.14", "R1",
        )
        update = make_mock_update(callback_data="refresh_routers")
        ctx = make_mock_context()
        await mod.refresh_routers(update, ctx)
        mod.ack_callback.return_value.edit_message_text \
            .assert_awaited()

    @pytest.mark.asyncio
    async def test_refresh_error(self):
        import bot.handlers.router_flows.saved as mod

        mod.ack_callback.return_value = AsyncMock()
        mod.run_blocking.side_effect = sqlite3.Error("fail")
        update = make_mock_update(callback_data="refresh_routers")
        ctx = make_mock_context()
        await mod.refresh_routers(update, ctx)
        mod.send_error.assert_awaited_once()
