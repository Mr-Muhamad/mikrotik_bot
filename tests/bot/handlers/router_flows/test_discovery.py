"""Tests for bot/handlers/router_flows/discovery.py — all handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.constants import WAITING_DISC_PASSWORD, WAITING_DISC_USERNAME
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.router_flows.discovery"


async def _call_through(fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(
        f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through
    ))
    stack.enter_context(patch(f"{P}.send_error", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.edit_clean", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.schedule_delete", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.ack_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.set_selected_router"))
    stack.enter_context(patch(f"{P}.log_action"))
    stack.enter_context(patch(f"{P}.get_router_by_ip", return_value=None))
    stack.enter_context(patch(f"{P}.get_router_display_name", return_value="OldRouter"))
    stack.enter_context(patch(
        f"{P}.save_discovered_router", new_callable=AsyncMock, return_value=1
    ))
    stack.enter_context(patch(f"{P}.update_router_credentials", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.mikrotik_api"))
    stack.enter_context(patch(f"{P}.reset_rate_limit"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestDiscoverRoutersCallback:
    @pytest.mark.asyncio
    async def test_success_with_routers(self):
        update = make_mock_update(user_id=724730774, callback_data="discover")
        context = make_mock_context()
        mock_router = MagicMock()
        mock_router.display_line.return_value = "Router 192.168.1.1"
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=query), patch(
            f"{P}.discover_routers", new_callable=AsyncMock, return_value=[mock_router]
        ):
            from bot.handlers.router_flows.discovery import discover_routers_callback

            await discover_routers_callback(update, context)
        query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_no_routers(self):
        update = make_mock_update(user_id=724730774, callback_data="discover")
        context = make_mock_context()
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=query), patch(
            f"{P}.discover_routers", new_callable=AsyncMock, return_value=[]
        ):
            from bot.handlers.router_flows.discovery import discover_routers_callback

            await discover_routers_callback(update, context)
        query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_permission_error(self):
        update = make_mock_update(user_id=724730774, callback_data="discover")
        context = make_mock_context()
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=query), patch(
            f"{P}.discover_routers", new_callable=AsyncMock, side_effect=PermissionError("no perms")
        ):
            from bot.handlers.router_flows.discovery import discover_routers_callback

            await discover_routers_callback(update, context)
        query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_general_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="discover")
        context = make_mock_context()
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=query), patch(
            f"{P}.discover_routers", new_callable=AsyncMock, side_effect=RuntimeError("net fail")
        ):
            from bot.handlers.router_flows.discovery import discover_routers_callback

            await discover_routers_callback(update, context)

    @pytest.mark.asyncio
    async def test_none_query(self):
        update = make_mock_update(user_id=724730774)
        update.callback_query = None
        context = make_mock_context()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=None):
            from bot.handlers.router_flows.discovery import discover_routers_callback

            await discover_routers_callback(update, context)


class TestDiscoveredRouterSelected:
    @pytest.mark.asyncio
    async def test_new_router_prompts_username(self):
        update = make_mock_update(user_id=724730774, callback_data="disc_router_192.168.1.1")
        context = make_mock_context()
        mock_query = MagicMock()
        mock_query.data = "disc_router_192.168.1.1"
        mock_query.from_user.id = 724730774
        mock_query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=mock_query), patch(
            f"{P}.get_router_by_ip", return_value=None
        ):
            from bot.handlers.router_flows.discovery import discovered_router_selected

            result = await discovered_router_selected(update, context)
        assert result == WAITING_DISC_USERNAME
        assert context.user_data["disc_ip"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_existing_router_with_username(self):
        update = make_mock_update(user_id=724730774, callback_data="disc_router_192.168.1.1")
        context = make_mock_context()
        mock_db = {"id": 5, "username": "admin", "identity": "OldRouter"}
        mock_query = MagicMock()
        mock_query.data = "disc_router_192.168.1.1"
        mock_query.from_user.id = 724730774
        mock_query.edit_message_text = AsyncMock()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=mock_query), patch(
            f"{P}.get_router_by_ip", return_value=mock_db
        ):
            from bot.handlers.router_flows.discovery import discovered_router_selected

            result = await discovered_router_selected(update, context)
        assert result == WAITING_DISC_PASSWORD

    @pytest.mark.asyncio
    async def test_none_query(self):
        update = make_mock_update(user_id=724730774)
        update.callback_query = None
        context = make_mock_context()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=None):
            from bot.handlers.router_flows.discovery import discovered_router_selected

            result = await discovered_router_selected(update, context)
        assert result is None


class TestDiscEnterUsername:
    @pytest.mark.asyncio
    async def test_stores_username_and_prompts_password(self):
        update = make_mock_update(user_id=724730774, text="admin")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        from bot.handlers.router_flows.discovery import disc_enter_username

        result = await disc_enter_username(update, context)
        assert result == WAITING_DISC_PASSWORD
        assert context.user_data["disc_username"] == "admin"


class TestDiscEnterPassword:
    @pytest.mark.asyncio
    async def test_connection_success_new_router(self):
        update = make_mock_update(user_id=724730774, text="pass123")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        context.user_data["disc_username"] = "admin"
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.test_connection = AsyncMock(return_value=(True, "7.12", "Router"))
            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.message_id = 10
            update.message.reply_text = AsyncMock(return_value=status_msg)
            stack.enter_context(patch(f"{P}.get_router_by_ip", return_value=None))
            stack.enter_context(patch(
                f"{P}.save_discovered_router",
                new_callable=AsyncMock, return_value=42,
            ))
            stack.enter_context(
                patch("core.router_info.detect_router_system", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch("core.watchdog.check_router_health", new_callable=AsyncMock)
            )
            from bot.handlers.router_flows.discovery import disc_enter_password

            result = await disc_enter_password(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_connection_success_existing_router(self):
        update = make_mock_update(user_id=724730774, text="pass123")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        context.user_data["disc_username"] = "admin"
        mock_db = {"id": 5}
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.test_connection = AsyncMock(return_value=(True, "7.12", "Router"))
            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.message_id = 10
            update.message.reply_text = AsyncMock(return_value=status_msg)
            stack.enter_context(patch(f"{P}.get_router_by_ip", return_value=mock_db))
            stack.enter_context(patch(f"{P}.update_router_credentials", new_callable=AsyncMock))
            stack.enter_context(
                patch("core.router_info.detect_router_system", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch("core.watchdog.check_router_health", new_callable=AsyncMock)
            )
            from bot.handlers.router_flows.discovery import disc_enter_password

            result = await disc_enter_password(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_connection_failed(self):
        update = make_mock_update(user_id=724730774, text="wrong")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        context.user_data["disc_username"] = "admin"
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.test_connection = AsyncMock(return_value=(False, "Auth failed", ""))
            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.message_id = 10
            update.message.reply_text = AsyncMock(return_value=status_msg)
            from bot.handlers.router_flows.discovery import disc_enter_password

            result = await disc_enter_password(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_exception_sends_error(self):
        update = make_mock_update(user_id=724730774, text="pass")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        context.user_data["disc_username"] = "admin"
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.test_connection = AsyncMock(side_effect=RuntimeError("net err"))
            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.message_id = 10
            update.message.reply_text = AsyncMock(return_value=status_msg)
            from bot.handlers.router_flows.discovery import disc_enter_password

            result = await disc_enter_password(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_delete_fails_gracefully(self):
        update = make_mock_update(user_id=724730774, text="pass")
        context = make_mock_context()
        context.user_data["disc_ip"] = "192.168.1.1"
        context.user_data["disc_username"] = "admin"
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.test_connection = AsyncMock(return_value=(True, "7.12", "R"))
            status_msg = MagicMock()
            status_msg.edit_text = AsyncMock()
            status_msg.message_id = 10
            update.message.reply_text = AsyncMock(return_value=status_msg)
            update.message.delete = AsyncMock(side_effect=RuntimeError("perm denied"))
            stack.enter_context(patch(f"{P}.get_router_by_ip", return_value=None))
            stack.enter_context(
                patch("core.router_info.detect_router_system", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch("core.watchdog.check_router_health", new_callable=AsyncMock)
            )
            from bot.handlers.router_flows.discovery import disc_enter_password

            result = await disc_enter_password(update, context)
        assert result == -1
