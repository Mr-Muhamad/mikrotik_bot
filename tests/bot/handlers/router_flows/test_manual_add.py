"""Tests for bot/handlers/router_flows/manual_add.py — all handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.router_flows.manual_add"


async def _call_through(fn, *args, **kwargs):  # type: ignore[reportMissingParameterType]
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _make_patches(**overrides):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
    """Return a list of context managers for patching all deps."""
    patches = [
        ("admin_decorator.ADMIN_IDS", [724730774]),
        (f"{P}.run_blocking", AsyncMock(side_effect=_call_through)),
        (f"{P}.send_error", AsyncMock()),
        (f"{P}.edit_clean", AsyncMock()),
        (f"{P}.send_step", AsyncMock()),
        (f"{P}.schedule_delete", AsyncMock()),
        (f"{P}.safe_answer_callback", AsyncMock()),
        (f"{P}.cleanup_state"),
        (f"{P}.nav_set"),
        (f"{P}.set_selected_router"),
        (f"{P}.log_action", AsyncMock()),
        (f"{P}.get_router_by_ip", AsyncMock(return_value=None)),
        (f"{P}.save_manual_router", AsyncMock(return_value=1)),
        (f"{P}.update_router_identity", AsyncMock()),
        (f"{P}.update_router_last_seen", AsyncMock()),
        (f"{P}.mikrotik_api"),
        (f"{P}.validate_ip", lambda x: (True, "")),
        (f"{P}.validate_port", lambda x: (True, "")),
        (f"{P}.validate_username", lambda x: (True, "")),
        (f"{P}.validate_password", lambda x: (True, "")),
        (f"{P}.get_main_keyboard", MagicMock()),
        (f"{P}.get_router_keyboard", MagicMock()),
    ]
    stack = ExitStack()
    for path, val in overrides.items():
        stack.enter_context(patch(path, val))
    for path, val in patches:
        if path not in overrides:
            stack.enter_context(patch(path, val))
    return stack


@pytest.fixture(autouse=True)
def _clean_rate_limits():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestManualAddStart:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_from_callback(self):
        update = make_mock_update(user_id=724730774, callback_data="manual_add")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        self.stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
        self.stack.enter_context(patch(f"{P}.cleanup_state"))
        self.stack.enter_context(patch(f"{P}.nav_set"))
        from bot.handlers.router_flows.manual_add import manual_add_start

        result = await manual_add_start(update, context)
        from bot.handlers.constants import WAITING_MANUAL_IP

        assert result == WAITING_MANUAL_IP

    @pytest.mark.asyncio
    async def test_from_message(self):
        update = make_mock_update(user_id=724730774, text="/addrouter")
        update.callback_query = None
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        self.stack.enter_context(patch(f"{P}.cleanup_state"))
        self.stack.enter_context(patch(f"{P}.nav_set"))
        from bot.handlers.router_flows.manual_add import manual_add_start

        result = await manual_add_start(update, context)
        from bot.handlers.constants import WAITING_MANUAL_IP

        assert result == WAITING_MANUAL_IP


class TestManualAddIp:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        self.stack.enter_context(patch(
            f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through
        ))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_valid_ip_stores_and_advances(self):
        update = make_mock_update(user_id=724730774, text="192.168.1.1")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.validate_ip", lambda x: (True, "")))
        self.stack.enter_context(
            patch(f"{P}.get_router_by_ip", AsyncMock(return_value=None))
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_ip

        result = await manual_add_ip(update, context)
        from bot.handlers.constants import WAITING_MANUAL_PORT

        assert result == WAITING_MANUAL_PORT
        assert context.user_data["manual_ip"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_invalid_ip_returns_same_state(self):
        update = make_mock_update(user_id=724730774, text="not_an_ip")
        context = make_mock_context()
        self.stack.enter_context(
            patch(f"{P}.validate_ip", lambda x: (False, "Invalid IP"))
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_ip

        result = await manual_add_ip(update, context)
        from bot.handlers.constants import WAITING_MANUAL_IP

        assert result == WAITING_MANUAL_IP

    @pytest.mark.asyncio
    async def test_duplicate_ip_returns_same_state(self):
        update = make_mock_update(user_id=724730774, text="192.168.1.1")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.validate_ip", lambda x: (True, "")))
        self.stack.enter_context(
            patch(
                f"{P}.get_router_by_ip",
                AsyncMock(return_value={"identity": "OldRouter"}),
            )
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_ip

        result = await manual_add_ip(update, context)
        from bot.handlers.constants import WAITING_MANUAL_IP

        assert result == WAITING_MANUAL_IP


class TestManualAddPort:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_empty_uses_default_port(self):
        update = make_mock_update(user_id=724730774, text="")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_port

        result = await manual_add_port(update, context)
        from bot.handlers.constants import WAITING_MANUAL_USER
        from config import DEFAULT_API_PORT

        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == DEFAULT_API_PORT

    @pytest.mark.asyncio
    async def test_valid_port(self):
        update = make_mock_update(user_id=724730774, text="8828")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.validate_port", lambda x: (True, "")))
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_port

        result = await manual_add_port(update, context)
        from bot.handlers.constants import WAITING_MANUAL_USER

        assert result == WAITING_MANUAL_USER
        assert context.user_data["manual_port"] == 8828

    @pytest.mark.asyncio
    async def test_invalid_port_returns_same_state(self):
        update = make_mock_update(user_id=724730774, text="99999")
        context = make_mock_context()
        self.stack.enter_context(
            patch(f"{P}.validate_port", lambda x: (False, "port too high"))
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_port

        result = await manual_add_port(update, context)
        from bot.handlers.constants import WAITING_MANUAL_PORT

        assert result == WAITING_MANUAL_PORT


class TestManualAddUser:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_valid_username(self):
        update = make_mock_update(user_id=724730774, text="admin")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.validate_username", lambda x: (True, "")))
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_user

        result = await manual_add_user(update, context)
        from bot.handlers.constants import WAITING_MANUAL_PASS

        assert result == WAITING_MANUAL_PASS
        assert context.user_data["manual_user"] == "admin"

    @pytest.mark.asyncio
    async def test_invalid_username(self):
        update = make_mock_update(user_id=724730774, text="")
        context = make_mock_context()
        self.stack.enter_context(
            patch(f"{P}.validate_username", lambda x: (False, "too short"))
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_user

        result = await manual_add_user(update, context)
        from bot.handlers.constants import WAITING_MANUAL_USER

        assert result == WAITING_MANUAL_USER


class TestManualAddPass:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_valid_password(self):
        update = make_mock_update(user_id=724730774, text="secret123")
        context = make_mock_context()
        self.stack.enter_context(patch(f"{P}.validate_password", lambda x: (True, "")))
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_pass

        result = await manual_add_pass(update, context)
        from bot.handlers.constants import WAITING_MANUAL_ALIAS

        assert result == WAITING_MANUAL_ALIAS
        assert context.user_data["manual_pass"] == "secret123"

    @pytest.mark.asyncio
    async def test_invalid_password(self):
        update = make_mock_update(user_id=724730774, text="")
        context = make_mock_context()
        self.stack.enter_context(
            patch(f"{P}.validate_password", lambda x: (False, "required"))
        )
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_pass

        result = await manual_add_pass(update, context)
        from bot.handlers.constants import WAITING_MANUAL_PASS

        assert result == WAITING_MANUAL_PASS


class TestManualAddAlias:
    def setup_method(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        self.stack.close()
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_with_alias(self):
        update = make_mock_update(user_id=724730774, text="MyRouter")
        context = make_mock_context()
        context.user_data["manual_ip"] = "1.1.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_alias

        result = await manual_add_alias(update, context)
        from bot.handlers.constants import WAITING_MANUAL_CONFIRM

        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == "MyRouter"

    @pytest.mark.asyncio
    async def test_skip_alias(self):
        update = make_mock_update(user_id=724730774, text="/skip")
        context = make_mock_context()
        context.user_data["manual_ip"] = "1.1.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_alias

        result = await manual_add_alias(update, context)
        from bot.handlers.constants import WAITING_MANUAL_CONFIRM

        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == ""

    @pytest.mark.asyncio
    async def test_empty_alias(self):
        update = make_mock_update(user_id=724730774, text="")
        context = make_mock_context()
        context.user_data["manual_ip"] = "1.1.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        self.stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
        from bot.handlers.router_flows.manual_add import manual_add_alias

        result = await manual_add_alias(update, context)
        from bot.handlers.constants import WAITING_MANUAL_CONFIRM

        assert result == WAITING_MANUAL_CONFIRM
        assert context.user_data["manual_alias"] == ""


class TestManualAddConfirm:
    def setup_method(self):
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    def teardown_method(self):
        admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_cancel_returns_end(self):
        from bot.handlers.callback_constants import manual_add_confirm as build_confirm

        update = make_mock_update(user_id=724730774, callback_data=build_confirm(False))
        context = make_mock_context()
        with ExitStack() as stack:
            stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
            stack.enter_context(
                patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
            )
            stack.enter_context(patch(f"{P}.cleanup_state"))
            stack.enter_context(
                patch(f"{P}.get_router_keyboard", MagicMock())
            )
            from bot.handlers.router_flows.manual_add import manual_add_confirm

            result = await manual_add_confirm(update, context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_success(self):
        from bot.handlers.callback_constants import manual_add_confirm as build_confirm

        update = make_mock_update(user_id=724730774, callback_data=build_confirm(True))
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        context.user_data["manual_pass"] = "secret"
        context.user_data["manual_alias"] = "R1"
        with ExitStack() as stack:
            stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
            stack.enter_context(
                patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
            )
            mock_api = MagicMock()
            mock_api.test_connection = MagicMock(return_value=(True, "7.12", "Router"))
            stack.enter_context(patch(f"{P}.mikrotik_api", mock_api))
            stack.enter_context(
                patch(f"{P}.save_manual_router", AsyncMock(return_value=42))
            )
            stack.enter_context(
                patch(f"{P}.update_router_last_seen", AsyncMock())
            )
            stack.enter_context(
                patch(f"{P}.update_router_identity", AsyncMock())
            )
            stack.enter_context(
                patch(f"{P}.run_blocking", AsyncMock(side_effect=_call_through))
            )
            stack.enter_context(
                patch(f"{P}.set_selected_router")
            )
            stack.enter_context(patch(f"{P}.log_action", AsyncMock()))
            stack.enter_context(patch(f"{P}.cleanup_state"))
            stack.enter_context(
                patch(f"{P}.get_main_keyboard", MagicMock())
            )
            stack.enter_context(patch("core.router_info.detect_router_system", AsyncMock()))
            stack.enter_context(patch("core.watchdog.check_router_health", AsyncMock()))
            from bot.handlers.router_flows.manual_add import manual_add_confirm

            result = await manual_add_confirm(update, context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END
        assert context.user_data.get("manual_ip") == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_confirm_duplicate_raises(self):
        from bot.handlers.callback_constants import manual_add_confirm as build_confirm
        from core.exceptions import RouterAlreadyExistsError

        update = make_mock_update(user_id=724730774, callback_data=build_confirm(True))
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        context.user_data["manual_pass"] = "secret"
        with ExitStack() as stack:
            stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
            stack.enter_context(
                patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch(
                    f"{P}.save_manual_router",
                    AsyncMock(side_effect=RouterAlreadyExistsError()),
                )
            )
            stack.enter_context(patch(f"{P}.cleanup_state"))
            stack.enter_context(
                patch(f"{P}.get_router_keyboard", MagicMock())
            )
            from bot.handlers.router_flows.manual_add import manual_add_confirm

            result = await manual_add_confirm(update, context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_generic_exception(self):
        from bot.handlers.callback_constants import manual_add_confirm as build_confirm

        update = make_mock_update(user_id=724730774, callback_data=build_confirm(True))
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        context.user_data["manual_pass"] = "secret"
        with ExitStack() as stack:
            stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
            stack.enter_context(
                patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch(
                    f"{P}.save_manual_router",
                    AsyncMock(side_effect=RuntimeError("db broken")),
                )
            )
            stack.enter_context(patch(f"{P}.send_error", AsyncMock()))
            stack.enter_context(patch(f"{P}.cleanup_state"))
            from bot.handlers.router_flows.manual_add import manual_add_confirm

            result = await manual_add_confirm(update, context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_connection_failed(self):
        from bot.handlers.callback_constants import manual_add_confirm as build_confirm

        update = make_mock_update(user_id=724730774, callback_data=build_confirm(True))
        context = make_mock_context()
        context.user_data["manual_ip"] = "192.168.1.1"
        context.user_data["manual_port"] = 8728
        context.user_data["manual_user"] = "admin"
        context.user_data["manual_pass"] = "secret"
        with ExitStack() as stack:
            stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
            stack.enter_context(
                patch(f"{P}.safe_answer_callback", new_callable=AsyncMock)
            )
            mock_api = MagicMock()
            mock_api.test_connection = MagicMock(return_value=(False, "Auth failed", ""))
            stack.enter_context(patch(f"{P}.mikrotik_api", mock_api))
            stack.enter_context(
                patch(f"{P}.save_manual_router", AsyncMock(return_value=42))
            )
            stack.enter_context(
                patch(f"{P}.run_blocking", AsyncMock(side_effect=_call_through))
            )
            stack.enter_context(patch(f"{P}.log_action", AsyncMock()))
            stack.enter_context(patch(f"{P}.cleanup_state"))
            stack.enter_context(
                patch(f"{P}.get_router_keyboard", MagicMock())
            )
            from bot.handlers.router_flows.manual_add import manual_add_confirm

            result = await manual_add_confirm(update, context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END
