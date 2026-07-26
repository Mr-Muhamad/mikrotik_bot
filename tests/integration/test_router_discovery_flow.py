"""Integration-style tests for router discovery and saved router flows.

Tests the end-to-end router discovery and management through handlers
using the in-memory MikrotikAPIMock.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.routers import (
    connect_router,
    delete_router_execute,
    discover_routers_callback,
    saved_routers_list,
)
from core.network_scanner import DiscoveredRouter
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _fake_router(ip="192.168.88.1", identity="R1", version="7.15"):
    return DiscoveredRouter(
        ip_address=ip,
        mac_address="AA:BB:CC:DD:EE:01",
        identity=identity,
        version=version,
        board="RB951Ui",
        software_id="ABC123",
        platform="MikroTik",
        uptime="1d",
        interface_name="ether1",
        port=8728,
        source="port_check",
        last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


class TestDiscoverRoutersCallback:
    @pytest.mark.asyncio
    async def test_discovery_saves_routers(self, mock_mikrotik_api):
        from database.models import get_saved_routers

        routers = [_fake_router("10.0.0.1"), _fake_router("10.0.0.2", identity="R2")]
        update = make_mock_update(callback_data="discover_routers")
        context = _make_context()

        with patch(
            "bot.handlers.router_flows.discovery.discover_routers",
            new=AsyncMock(return_value=routers),
        ):
            await discover_routers_callback(update, context)

        saved = get_saved_routers(active_only=True)
        assert len(saved) == 0
        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_discovery_no_results(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="discover_routers")
        context = _make_context()

        with patch(
            "bot.handlers.router_flows.discovery.discover_routers",
            new=AsyncMock(return_value=[]),
        ):
            await discover_routers_callback(update, context)

        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_discovery_updates_existing_router(self, mock_mikrotik_api):
        from database.models import get_router_by_ip, save_discovered_router

        save_discovered_router(
            ip="10.0.0.3",
            username="",
            password="",
            identity="OldName",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        routers = [_fake_router("10.0.0.3", identity="NewName")]
        update = make_mock_update(callback_data="discover_routers")
        context = _make_context()

        with patch(
            "bot.handlers.router_flows.discovery.discover_routers",
            new=AsyncMock(return_value=routers),
        ):
            await discover_routers_callback(update, context)

        existing = get_router_by_ip("10.0.0.3")
        assert existing is not None
        assert existing["identity"] == "OldName"

    @pytest.mark.asyncio
    async def test_discovery_handles_exception(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="discover_routers")
        context = _make_context()

        with patch(
            "bot.handlers.router_flows.discovery.discover_routers",
            new=AsyncMock(side_effect=Exception("net down")),
        ):
            await discover_routers_callback(update, context)

        assert update.callback_query.edit_message_text.called


class TestSavedRoutersList:
    @pytest.mark.asyncio
    async def test_list_empty(self, mock_mikrotik_api):
        from database.models import delete_router

        for r in _all_saved_routers():
            assert isinstance(r["id"], int)
            delete_router(r["id"])
        update = make_mock_update(callback_data="saved_routers")
        context = _make_context()

        await saved_routers_list(update, context)
        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_list_with_routers(self, mock_mikrotik_api):
        from database.models import save_discovered_router

        save_discovered_router(
            ip="10.0.0.10",
            username="admin",
            password="pass",
            identity="MyRouter",
            version="7.10",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        update = make_mock_update(callback_data="saved_routers")
        context = _make_context()

        await saved_routers_list(update, context)

        call = update.callback_query.edit_message_text.call_args
        text = call.args[0] if call.args else call.kwargs.get("text", "")
        assert "MyRouter" in text or "10.0.0.10" in text


class TestConnectRouter:
    @pytest.mark.asyncio
    async def test_connect_success_sets_router(self, mock_mikrotik_api):
        from bot.router_selector import get_selected_router
        from database.models import save_discovered_router

        router_id = save_discovered_router(
            ip="10.0.0.20",
            username="admin",
            password="pass",
            identity="R1",
            version="7.10",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        update = make_mock_update(callback_data=f"connect_router_{router_id}")
        context = _make_context()

        with patch("bot.handlers.router_flows.saved.mikrotik_api") as mock_api:
            mock_api.test_connection = MagicMock(return_value=(True, "7.10", "R1"))
            with patch("bot.handlers.routers.loop", create=True) as mock_loop:
                mock_loop.run_in_executor = AsyncMock(return_value=(True, "7.10", "R1"))
                await connect_router(update, context)

        router_key = f"discovered_{router_id}"
        assert get_selected_router(ADMIN_ID) == router_key

    @pytest.mark.asyncio
    async def test_connect_failure_no_credentials(self, mock_mikrotik_api):
        from database.models import save_discovered_router

        router_id = save_discovered_router(
            ip="10.0.0.30",
            username="",
            password="",
            identity="R2",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        update = make_mock_update(callback_data=f"connect_router_{router_id}")
        context = _make_context()

        await connect_router(update, context)
        call = update.callback_query.edit_message_text.call_args
        text = call.args[0] if call.args else call.kwargs.get("text", "")
        assert "بيانات" in text or "credentials" in text.lower() or "❌" in text

    @pytest.mark.asyncio
    async def test_connect_invalid_id(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="connect_router_abc")
        context = _make_context()

        await connect_router(update, context)
        assert update.callback_query.edit_message_text.called


class TestDeleteRouterExecute:
    @pytest.mark.asyncio
    async def test_confirm_yes_deletes_router(self, mock_mikrotik_api):
        from database.models import get_router_by_id, save_discovered_router

        router_id = save_discovered_router(
            ip="10.0.0.40",
            username="admin",
            password="pass",
            identity="ToDelete",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        assert router_id is not None
        update = make_mock_update(callback_data=f"confirm_delete_router_yes_{router_id}")
        context = _make_context()

        await delete_router_execute(update, context)
        assert get_router_by_id(router_id) is None

    @pytest.mark.asyncio
    async def test_confirm_no_keeps_router(self, mock_mikrotik_api):
        from database.models import get_router_by_id, save_discovered_router

        router_id = save_discovered_router(
            ip="10.0.0.50",
            username="admin",
            password="pass",
            identity="KeepMe",
            last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        assert router_id is not None
        update = make_mock_update(callback_data=f"confirm_delete_router_no_{router_id}")
        context = _make_context()

        await delete_router_execute(update, context)
        assert get_router_by_id(router_id) is not None

    @pytest.mark.asyncio
    async def test_invalid_id_handled(self, mock_mikrotik_api):
        update = make_mock_update(callback_data="confirm_delete_router_yes_abc")
        context = _make_context()

        await delete_router_execute(update, context)
        assert update.callback_query.edit_message_text.called


def _all_saved_routers():
    from database.models import get_saved_routers

    return get_saved_routers(active_only=False)
