"""Tests for bot/handlers/router_flows/reboot.py — all handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.router_flows.reboot"


async def _call_through(fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _make_query_mock():
    q = MagicMock()
    q.edit_message_text = AsyncMock()
    return q


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(patch(f"{P}.get_selected_router", return_value="discovered_1"))
    stack.enter_context(
        patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through)
    )
    stack.enter_context(patch(f"{P}.send_and_track", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.clean_command", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.mikrotik_api"))
    stack.enter_context(patch(f"{P}.log_action"))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.is_duplicate_callback", return_value=False))
    stack.enter_context(patch(f"{P}.schedule_delete", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.ack_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.parse_router_id", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_router_by_id", return_value=None))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestRebootStart:
    @pytest.mark.asyncio
    async def test_no_selected_router_sends_error(self):
        with patch(f"{P}.get_selected_router", return_value=None):
            mock_track = patch(f"{P}.send_and_track", new_callable=AsyncMock)
            with mock_track as mt:
                update = make_mock_update(user_id=724730774)
                context = make_mock_context()
                from bot.handlers.router_flows.reboot import reboot_start

                await reboot_start(update, context)
                mt.assert_called_once()
                sent_text = mt.call_args[0][2]
                assert "اختر راوتر" in sent_text

    @pytest.mark.asyncio
    async def test_with_selected_router_sends_confirm(self):
        with ExitStack() as stack:
            stack.enter_context(patch(f"{P}.get_selected_router", return_value="discovered_1"))
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.get_router_name.return_value = "TestRouter"
            mt = stack.enter_context(
                patch(f"{P}.send_and_track", new_callable=AsyncMock)
            )
            update = make_mock_update(user_id=724730774)
            context = make_mock_context()
            from bot.handlers.router_flows.reboot import reboot_start

            await reboot_start(update, context)
            mt.assert_called_once()
            sent_text = mt.call_args[0][2]
            assert "إعادة تشغيل" in sent_text


class TestRebootRouterCallback:
    @pytest.mark.asyncio
    async def test_reboot_no_edits_cancelled(self):
        update = make_mock_update(user_id=724730774, callback_data="reboot_no")
        context = make_mock_context()
        from bot.handlers.router_flows.reboot import reboot_router_callback

        await reboot_router_callback(update, context)
        update.callback_query.edit_message_text.assert_called_once()
        sent_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "إلغاء" in sent_text

    @pytest.mark.asyncio
    async def test_reboot_yes_executes_reboot(self):
        update = make_mock_update(user_id=724730774, callback_data="reboot_yes_discovered_1")
        context = make_mock_context()
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            from bot.handlers.router_flows.reboot import reboot_router_callback

            await reboot_router_callback(update, context)

        mock_api.execute_non_blocking.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_yes_empty_key_sends_error(self):
        update = make_mock_update(user_id=724730774, callback_data="reboot_yes_")
        context = make_mock_context()
        from bot.handlers.router_flows.reboot import reboot_router_callback

        await reboot_router_callback(update, context)
        update.callback_query.edit_message_text.assert_called_once()
        sent_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "اختر راوتر" in sent_text

    @pytest.mark.asyncio
    async def test_reboot_yes_exception_still_shows_success(self):
        update = make_mock_update(user_id=724730774, callback_data="reboot_yes_discovered_1")
        context = make_mock_context()
        with ExitStack() as stack:
            mock_api = stack.enter_context(patch(f"{P}.mikrotik_api"))
            mock_api.execute_non_blocking.side_effect = OSError("Connection lost")
            from bot.handlers.router_flows.reboot import reboot_router_callback

            await reboot_router_callback(update, context)

        edit_calls = update.callback_query.edit_message_text.call_args_list
        last_text = edit_calls[-1][0][0]
        assert "إعادة تشغيل" in last_text

    @pytest.mark.asyncio
    async def test_duplicate_callback_is_ignored(self):
        with patch(f"{P}.is_duplicate_callback", return_value=True):
            update = make_mock_update(user_id=724730774, callback_data="reboot_yes_x")
            context = make_mock_context()
            from bot.handlers.router_flows.reboot import reboot_router_callback

            await reboot_router_callback(update, context)
            update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_query_returns_early(self):
        update = make_mock_update(user_id=724730774)
        update.callback_query = None
        context = make_mock_context()
        from bot.handlers.router_flows.reboot import reboot_router_callback

        await reboot_router_callback(update, context)
        context.bot.send_message.assert_not_called()


class TestRebootSavedRouter:
    @pytest.mark.asyncio
    async def test_valid_router_id_shows_confirm(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.parse_router_id", new_callable=AsyncMock, return_value=42)
            )
            stack.enter_context(
                patch(
                    f"{P}.get_router_by_id",
                    return_value={"identity": "MyRouter", "ip_address": "10.0.0.1"},
                )
            )
            mock_ack = stack.enter_context(
                patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=_make_query_mock())
            )
            from bot.handlers.router_flows.reboot import reboot_saved_router

            update = make_mock_update(user_id=724730774, callback_data="reboot_router_42")
            context = make_mock_context()
            await reboot_saved_router(update, context)

        query = mock_ack.return_value
        query.edit_message_text.assert_called_once()
        sent_text = query.edit_message_text.call_args[0][0]
        assert "إعادة تشغيل" in sent_text

    @pytest.mark.asyncio
    async def test_router_not_found_shows_error(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.parse_router_id", new_callable=AsyncMock, return_value=999)
            )
            stack.enter_context(
                patch(f"{P}.get_router_by_id", return_value=None)
            )
            mock_ack = stack.enter_context(
                patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=_make_query_mock())
            )
            from bot.handlers.router_flows.reboot import reboot_saved_router

            update = make_mock_update(user_id=724730774, callback_data="reboot_router_999")
            context = make_mock_context()
            await reboot_saved_router(update, context)

        query = mock_ack.return_value
        query.edit_message_text.assert_called_once()
        sent_text = query.edit_message_text.call_args[0][0]
        assert "غير موجود" in sent_text or "not found" in sent_text.lower()

    @pytest.mark.asyncio
    async def test_invalid_router_id_shows_error(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.parse_router_id", new_callable=AsyncMock, return_value=None)
            )
            mock_ack = stack.enter_context(
                patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=_make_query_mock())
            )
            from bot.handlers.router_flows.reboot import reboot_saved_router

            update = make_mock_update(user_id=724730774, callback_data="reboot_router_abc")
            context = make_mock_context()
            await reboot_saved_router(update, context)

        query = mock_ack.return_value
        query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_query_returns_early(self):
        update = make_mock_update(user_id=724730774)
        update.callback_query = None
        context = make_mock_context()
        with patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=None):
            from bot.handlers.router_flows.reboot import reboot_saved_router

            await reboot_saved_router(update, context)

    @pytest.mark.asyncio
    async def test_router_with_ip_fallback_name(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(f"{P}.parse_router_id", new_callable=AsyncMock, return_value=1)
            )
            stack.enter_context(
                patch(f"{P}.get_router_by_id", return_value={"ip_address": "192.168.1.1"})
            )
            mock_ack = stack.enter_context(
                patch(f"{P}.ack_callback", new_callable=AsyncMock, return_value=_make_query_mock())
            )
            from bot.handlers.router_flows.reboot import reboot_saved_router

            update = make_mock_update(user_id=724730774, callback_data="reboot_router_1")
            context = make_mock_context()
            await reboot_saved_router(update, context)

        query = mock_ack.return_value
        sent_text = query.edit_message_text.call_args[0][0]
        assert "192.168.1.1" in sent_text
