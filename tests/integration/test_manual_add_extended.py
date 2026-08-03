"""Extended tests for the manual router-add flow — covers all handlers.

Tests manual_add_start, manual_add_ip, manual_add_port, manual_add_user,
manual_add_pass, manual_add_alias, and manual_add_confirm (yes/no paths,
error paths, edge cases).
"""

from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.callback_constants import manual_add_confirm as build_manual_add_confirm
from bot.handlers.constants import (
    WAITING_MANUAL_ALIAS,
    WAITING_MANUAL_CONFIRM,
    WAITING_MANUAL_IP,
    WAITING_MANUAL_PASS,
    WAITING_MANUAL_PORT,
    WAITING_MANUAL_USER,
)
from bot.handlers.router_flows.manual_add import (
    manual_add_alias,
    manual_add_confirm,
    manual_add_ip,
    manual_add_pass,
    manual_add_port,
    manual_add_start,
    manual_add_user,
)
from core.exceptions import RouterAlreadyExistsError
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


# ── manual_add_start ─────────────────────────────────────────────────
class TestManualAddStart:
    @pytest.mark.asyncio
    async def test_start_from_callback(self):
        update = make_mock_update(callback_data="manual_add")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.cleanup_state"), \
             patch("bot.handlers.router_flows.manual_add.nav_set"):
            result = await manual_add_start(update, context)
        assert result == WAITING_MANUAL_IP
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_from_message(self):
        update = make_mock_update(text="/addrouter")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.cleanup_state"), \
             patch("bot.handlers.router_flows.manual_add.nav_set"):
            result = await manual_add_start(update, context)
        assert result == WAITING_MANUAL_IP
        update.message.reply_text.assert_awaited_once()


# ── manual_add_ip ────────────────────────────────────────────────────
class TestManualAddIp:
    @pytest.mark.asyncio
    async def test_valid_ip(self):
        update = make_mock_update(text="192.168.1.100")
        context = make_mock_context()
        run_p = patch(
            "bot.handlers.router_flows.manual_add.run_blocking",
            new_callable=AsyncMock,
            return_value=None,
        )
        send_p = patch(
            "bot.handlers.router_flows.manual_add.send_step",
            new_callable=AsyncMock,
        )
        with run_p, send_p:
            result = await manual_add_ip(update, context)
        assert result == WAITING_MANUAL_PORT
        assert context.user_data["manual_ip"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_invalid_ip(self):
        update = make_mock_update(text="not_an_ip")
        context = make_mock_context()
        send_p = patch(
            "bot.handlers.router_flows.manual_add.send_step",
            new_callable=AsyncMock,
        )
        with send_p as mock_send:
            result = await manual_add_ip(update, context)
        assert result == WAITING_MANUAL_IP
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_ip(self):
        update = make_mock_update(text="10.0.0.1")
        context = make_mock_context()
        existing = {"ip": "10.0.0.1", "identity": "existing_router"}
        run_p = patch(
            "bot.handlers.router_flows.manual_add.run_blocking",
            new_callable=AsyncMock,
            return_value=existing,
        )
        send_p = patch(
            "bot.handlers.router_flows.manual_add.send_step",
            new_callable=AsyncMock,
        )
        with run_p, send_p as mock_send:
            result = await manual_add_ip(update, context)
        assert result == WAITING_MANUAL_IP
        call_args = mock_send.call_args
        assert "10.0.0.1" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_ipv6_valid(self):
        update = make_mock_update(text="::1")
        context = make_mock_context()
        run_p = patch(
            "bot.handlers.router_flows.manual_add.run_blocking",
            new_callable=AsyncMock,
            return_value=None,
        )
        send_p = patch(
            "bot.handlers.router_flows.manual_add.send_step",
            new_callable=AsyncMock,
        )
        with run_p, send_p:
            result = await manual_add_ip(update, context)
        assert result == WAITING_MANUAL_PORT


# ── manual_add_port ──────────────────────────────────────────────────
class TestManualAddPort:
    @pytest.mark.asyncio
    async def test_empty_uses_default(self):
        update = make_mock_update(text="")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == 8728

    @pytest.mark.asyncio
    async def test_valid_port(self):
        update = make_mock_update(text="8729")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == 8729

    @pytest.mark.asyncio
    async def test_invalid_port_zero(self):
        update = make_mock_update(text="0")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_PORT

    @pytest.mark.asyncio
    async def test_invalid_port_over_65535(self):
        update = make_mock_update(text="70000")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_PORT

    @pytest.mark.asyncio
    async def test_invalid_port_non_numeric(self):
        update = make_mock_update(text="abc")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_PORT

    @pytest.mark.asyncio
    async def test_port_boundary_1(self):
        update = make_mock_update(text="1")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == 1

    @pytest.mark.asyncio
    async def test_port_boundary_65535(self):
        update = make_mock_update(text="65535")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_port(update, context)
        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == 65535


# ── manual_add_user ──────────────────────────────────────────────────
class TestManualAddUser:
    @pytest.mark.asyncio
    async def test_valid_username(self):
        update = make_mock_update(text="admin")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_user(update, context)
        assert result == WAITING_MANUAL_PASS
        assert context.user_data["manual_user"] == "admin"

    @pytest.mark.asyncio
    async def test_invalid_short_username(self):
        update = make_mock_update(text="ab")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_user(update, context)
        assert result == WAITING_MANUAL_USER

    @pytest.mark.asyncio
    async def test_invalid_special_chars(self):
        update = make_mock_update(text="user name!")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_user(update, context)
        assert result == WAITING_MANUAL_USER

    @pytest.mark.asyncio
    async def test_valid_with_dots_and_hyphens(self):
        update = make_mock_update(text="user.name-test")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_user(update, context)
        assert result == WAITING_MANUAL_PASS
        assert context.user_data["manual_user"] == "user.name-test"

    @pytest.mark.asyncio
    async def test_username_too_long(self):
        update = make_mock_update(text="a" * 65)
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_user(update, context)
        assert result == WAITING_MANUAL_USER


# ── manual_add_pass ──────────────────────────────────────────────────
class TestManualAddPass:
    @pytest.mark.asyncio
    async def test_valid_password(self):
        update = make_mock_update(text="secret123")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_pass(update, context)
        assert result == WAITING_MANUAL_ALIAS
        assert context.user_data["manual_pass"] == "secret123"

    @pytest.mark.asyncio
    async def test_invalid_short_password(self):
        update = make_mock_update(text="abc")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_pass(update, context)
        assert result == WAITING_MANUAL_PASS

    @pytest.mark.asyncio
    async def test_invalid_password_with_newline(self):
        update = make_mock_update(text="pass\nword")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_pass(update, context)
        assert result == WAITING_MANUAL_PASS

    @pytest.mark.asyncio
    async def test_invalid_password_with_tab(self):
        update = make_mock_update(text="pass\tword")
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_pass(update, context)
        assert result == WAITING_MANUAL_PASS

    @pytest.mark.asyncio
    async def test_password_too_long(self):
        update = make_mock_update(text="a" * 65)
        context = make_mock_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_pass(update, context)
        assert result == WAITING_MANUAL_PASS


# ── manual_add_alias ─────────────────────────────────────────────────
class TestManualAddAlias:
    def _setup_context(self):
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        return context

    @pytest.mark.asyncio
    async def test_valid_alias(self):
        update = make_mock_update(text="my_router")
        context = self._setup_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_alias(update, context)
        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == "my_router"

    @pytest.mark.asyncio
    async def test_skip_command(self):
        update = make_mock_update(text="/skip")
        context = self._setup_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_alias(update, context)
        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == ""

    @pytest.mark.asyncio
    async def test_empty_string(self):
        update = make_mock_update(text="")
        context = self._setup_context()
        with patch("bot.handlers.router_flows.manual_add.send_step", new_callable=AsyncMock):
            result = await manual_add_alias(update, context)
        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == ""


# ── manual_add_confirm ───────────────────────────────────────────────
class TestManualAddConfirm:
    def _setup_context(self):
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.50"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        context.user_data["manual_pass"] = "secret"
        context.user_data["manual_alias"] = "test_router"
        return context

    @pytest.mark.asyncio
    async def test_cancel(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(False))
        context = self._setup_context()
        with patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirm_success(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock()
        mock_run.side_effect = [
            42,  # save_manual_router returns router_id
            (True, "7.12", "RouterOS"),  # test_connection
            None,  # update_router_last_seen
            None,  # update_router_identity
            None,  # check_router_health
            None,  # detect_router_system
            None,  # log_action
        ]
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.set_selected_router") as mock_set, \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END
        mock_set.assert_called_once_with(ADMIN_ID, "discovered_42")

    @pytest.mark.asyncio
    async def test_confirm_connection_failed(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock()
        mock_run.side_effect = [
            42,  # save_manual_router
            (False, "Connection refused", ""),  # test_connection
            None,  # log_action
        ]
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirm_duplicate_router(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock(side_effect=RouterAlreadyExistsError("exists"))
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_save_exception(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock(side_effect=Exception("db error"))
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.send_error", new_callable=AsyncMock), \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_test_connection_exception(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock()
        mock_run.side_effect = [
            42,  # save_manual_router succeeds
            Exception("connection timeout"),  # test_connection fails
            None,  # log_action
        ]
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_identity_unknown(self):
        update = make_mock_update(callback_data=build_manual_add_confirm(True))
        context = self._setup_context()

        mock_run = AsyncMock()
        mock_run.side_effect = [
            42,  # save_manual_router
            (True, "7.12", "Unknown"),  # test_connection returns Unknown identity
            None,  # update_router_last_seen
            None,  # check_router_health
            None,  # detect_router_system
            None,  # log_action
        ]
        with patch("bot.handlers.router_flows.manual_add.run_blocking", mock_run), \
             patch("bot.handlers.router_flows.manual_add.set_selected_router"), \
             patch("bot.handlers.router_flows.manual_add.cleanup_state"):
            result = await manual_add_confirm(update, context)

        assert result == ConversationHandler.END
