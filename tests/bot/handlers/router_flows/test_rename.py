"""Tests for bot/handlers/router_flows/rename.py — rename conversation flow."""

import sqlite3
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from bot.handlers.constants import WAITING_RENAME
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.router_flows.rename"


async def _call_through(fn, *args, **kwargs):  # type: ignore[reportMissingParameterType]
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(
        patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through)
    )
    stack.enter_context(patch(f"{P}.send_error", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.reply_final", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.is_duplicate_callback", return_value=False))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.mikrotik_api"))
    stack.enter_context(patch(f"{P}.get_router_by_id", return_value=None))
    stack.enter_context(patch(f"{P}.get_router_display_name", return_value="OldName"))
    stack.enter_context(patch(f"{P}.get_saved_routers", return_value=[]))
    stack.enter_context(patch(f"{P}.update_router_alias"))
    stack.enter_context(patch(f"{P}.log_action"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestRenameRouterStart:
    @pytest.mark.asyncio
    async def test_valid_router_id_returns_waiting_rename(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value={"identity": "MyRouter", "ip_address": "10.0.0.1"},
                )
            )
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_5")
            context = make_mock_context()
            result = await rename_router_start(update, context)

        assert result == WAITING_RENAME
        assert context.user_data["rename_router_id"] == 5

    @pytest.mark.asyncio
    async def test_invalid_callback_data_returns_end(self):
        with patch(f"{P}.is_duplicate_callback", return_value=False):
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_abc")
            context = make_mock_context()
            from telegram.ext import ConversationHandler

            result = await rename_router_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_router_not_found_returns_end(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value=None,
                )
            )
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_99")
            context = make_mock_context()
            from telegram.ext import ConversationHandler

            result = await rename_router_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_duplicate_callback_returns_end(self):
        with patch(f"{P}.is_duplicate_callback", return_value=True):
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_1")
            context = make_mock_context()
            from telegram.ext import ConversationHandler

            result = await rename_router_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception_returns_end_and_logs_error(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    side_effect=sqlite3.Error("DB crash"),
                )
            )
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_1")
            context = make_mock_context()
            from telegram.ext import ConversationHandler

            result = await rename_router_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_displays_current_name(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value={"identity": "RouterX"},
                )
            )
            stack.enter_context(
                patch(f"{P}.get_router_display_name", return_value="RouterX")
            )
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_1")
            context = make_mock_context()
            await rename_router_start(update, context)

        update.callback_query.edit_message_text.assert_called_once()
        sent_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "RouterX" in sent_text

    @pytest.mark.asyncio
    async def test_stores_router_id_in_user_data(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value={"identity": "R"},
                )
            )
            from bot.handlers.router_flows.rename import rename_router_start

            update = make_mock_update(user_id=724730774, callback_data="rename_router_42")
            context = make_mock_context()
            await rename_router_start(update, context)

        assert context.user_data["rename_router_id"] == 42


class TestRenameRouterValue:
    @pytest.mark.asyncio
    async def test_empty_name_returns_waiting(self):
        update = make_mock_update(user_id=724730774, text="   ")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 1

        from bot.handlers.router_flows.rename import rename_router_value

        result = await rename_router_value(update, context)

        assert result == WAITING_RENAME

    @pytest.mark.asyncio
    async def test_valid_name_updates_alias_and_returns_end(self):
        update = make_mock_update(user_id=724730774, text="NewName")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 1

        with ExitStack() as stack:
            mock_update_alias = stack.enter_context(
                patch(f"{P}.update_router_alias")
            )
            stack.enter_context(
                patch(f"{P}.log_action")
            )
            from bot.handlers.router_flows.rename import rename_router_value

            result = await rename_router_value(update, context)

        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END
        mock_update_alias.assert_called_once_with(1, "NewName")

    @pytest.mark.asyncio
    async def test_missing_router_id_returns_end(self):
        update = make_mock_update(user_id=724730774, text="NewName")
        context = make_mock_context()
        context.user_data = {}

        from bot.handlers.router_flows.rename import rename_router_value

        result = await rename_router_value(update, context)

        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception_returns_end_and_calls_send_error(self):
        update = make_mock_update(user_id=724730774, text="NewName")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 1

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    f"{P}.update_router_alias",
                    side_effect=sqlite3.Error("DB error"),
                )
            )
            mock_send_error = stack.enter_context(
                patch(f"{P}.send_error", new_callable=AsyncMock)
            )
            from bot.handlers.router_flows.rename import rename_router_value

            result = await rename_router_value(update, context)

        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END
        mock_send_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_rename_invalidates_caches(self):
        update = make_mock_update(user_id=724730774, text="FreshName")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 7

        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            stack.enter_context(
                patch(f"{P}.update_router_alias")
            )
            from bot.handlers.router_flows.rename import rename_router_value

            await rename_router_value(update, context)

        mock_api.invalidate_router_name.assert_called_once_with("discovered_7")
        mock_api.invalidate_version.assert_called_once_with("discovered_7")

    @pytest.mark.asyncio
    async def test_successful_rename_clears_user_data(self):
        update = make_mock_update(user_id=724730774, text="Cleared")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 3
        context.user_data["some_other_key"] = "value"

        with ExitStack() as stack:
            mock_cleanup = stack.enter_context(
                patch(f"{P}.cleanup_state")
            )
            stack.enter_context(
                patch(f"{P}.update_router_alias")
            )
            from bot.handlers.router_flows.rename import rename_router_value

            await rename_router_value(update, context)

        mock_cleanup.assert_called_once_with(724730774, context.user_data)

    @pytest.mark.asyncio
    async def test_exception_clears_user_data(self):
        update = make_mock_update(user_id=724730774, text="Fail")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 2

        with ExitStack() as stack:
            mock_cleanup = stack.enter_context(
                patch(f"{P}.cleanup_state")
            )
            stack.enter_context(
                patch(
                    f"{P}.update_router_alias",
                    side_effect=sqlite3.Error("fail"),
                )
            )
            from bot.handlers.router_flows.rename import rename_router_value

            await rename_router_value(update, context)

        mock_cleanup.assert_called_once_with(724730774, context.user_data)

    @pytest.mark.asyncio
    async def test_logs_action_with_correct_args(self):
        update = make_mock_update(user_id=724730774, text="LoggedName")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 10

        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.update_router_alias")
            )
            mock_log = stack.enter_context(
                patch(f"{P}.log_action")
            )
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value={"identity": "OldRouter"},
                )
            )
            from bot.handlers.router_flows.rename import rename_router_value

            await rename_router_value(update, context)

        mock_log.assert_called_once_with(
            "rename_router", "LoggedName", "OldRouter", 724730774
        )

    @pytest.mark.asyncio
    async def test_sends_final_success_message(self):
        update = make_mock_update(user_id=724730774, text="Final")
        context = make_mock_context()
        context.user_data["rename_router_id"] = 1

        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.update_router_alias")
            )
            mock_reply = stack.enter_context(
                patch(f"{P}.reply_final", new_callable=AsyncMock)
            )
            from bot.handlers.router_flows.rename import rename_router_value

            await rename_router_value(update, context)

        mock_reply.assert_called_once()
        sent_text = mock_reply.call_args[0][2]
        assert "Final" in sent_text
