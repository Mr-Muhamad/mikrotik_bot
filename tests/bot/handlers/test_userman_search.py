"""Tests for bot.handlers.userman_search."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_USERMAN_SEARCH
from bot.handlers.userman_search import (
    userman_search_action,
    userman_search_add_profile,
    userman_search_add_profile_selected,
    userman_search_back,
    userman_search_query,
    userman_search_select,
    userman_search_start,
)
from bot.messages import USERMAN_SEARCH_PROMPT
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = MagicMock()
    return ctx


def _admin_update(**kwargs):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    chat = MagicMock()
    chat.type = "private"
    update.effective_chat = chat
    for k, v in kwargs.items():
        setattr(update, k, v)
    return update


class TestUsermanSearchStart:
    @pytest.mark.asyncio
    async def test_start_with_callback(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "userman_search"
        update.callback_query = query

        with patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()):
            result = await userman_search_start(update, _ctx())
        assert result == WAITING_USERMAN_SEARCH

    @pytest.mark.asyncio
    async def test_start_without_callback(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID)
        update.effective_chat = MagicMock(type="private")
        update.callback_query = None
        update.message = MagicMock()

        with patch("bot.handlers.userman_search.send_step", new=AsyncMock()):
            result = await userman_search_start(update, _ctx())
        assert result == WAITING_USERMAN_SEARCH

    @pytest.mark.asyncio
    async def test_registered_as_main_entry_point(self):
        import bot.registrations  # noqa: F401  (populates the handler registry)
        from utils.handler_registry import _registry

        matches = [
            e for e in _registry["entry_points"] if e["func"].__name__ == "userman_search_start"
        ]
        assert matches, "userman_search_start must be a main ConversationHandler entry point"
        assert matches[0]["cls"].__name__ == "CallbackQueryHandler"
        assert matches[0]["kwargs"].get("pattern") == r"^userman_search$"


class TestUsermanSearchQuery:
    @pytest.mark.asyncio
    async def test_no_router_ends(self):
        update = _admin_update()
        update.message = MagicMock()
        update.message.text = "ali"
        context = _ctx()

        with (
            patch("bot.handlers.userman_search.get_selected_router", return_value=None),
            patch("bot.handlers.userman_search.reply_final", new=AsyncMock()) as mock_reply,
        ):
            result = await userman_search_query(update, context)
        assert result == ConversationHandler.END
        mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_success(self):
        update = _admin_update()
        update.message = MagicMock()
        update.message.text = "ali"
        context = _ctx()

        users = [{"name": "ali", "profile": "default", "disabled": "false"}]
        loading = MagicMock()
        loading.message_id = 999

        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.userman_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.userman_search.send_step", new=AsyncMock()),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=users),
            ),
        ):
            result = await userman_search_query(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["search_um_hosts"] == users

    @pytest.mark.asyncio
    async def test_exception_returns_to_search(self):
        update = _admin_update()
        update.message = MagicMock()
        update.message.text = "x"
        context = _ctx()

        loading = MagicMock()
        loading.message_id = 999

        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.userman_search.delete_now", new=AsyncMock()),
            patch("bot.handlers.userman_search.send_step", new=AsyncMock()),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(side_effect=Exception("net down")),
            ),
        ):
            result = await userman_search_query(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["search_um_hosts"] == []


class TestUsermanSearchSelect:
    @pytest.mark.asyncio
    async def test_select_success(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_sel_0"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]

        result = await userman_search_select(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["kick_um_idx"] == 0

    @pytest.mark.asyncio
    async def test_select_invalid_index(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_sel_99"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali"}]

        with patch("bot.handlers.userman_search.safe_edit_plain", new=AsyncMock()):
            result = await userman_search_select(update, context)
        assert result == WAITING_USERMAN_SEARCH


class TestUsermanSearchAction:
    @pytest.mark.asyncio
    async def test_duplicate_callback_returns(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_delete"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=True),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
        ):
            result = await userman_search_action(update, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_router_ends(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_kick_execute"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch("bot.handlers.userman_search.get_selected_router", return_value=None),
        ):
            result = await userman_search_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reset_counters_error_passes_context_not_error_string(self):
        # Regression: safe_edit_plain must receive `context` as the 2nd
        # positional argument. A prior bug passed the error string there
        # (and the keyboard as text), causing "'str' object has no attribute
        # 'bot_data'" when the error path was hit (e.g. reset counters failed).
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_reset_counters"
        query.edit_message_text = AsyncMock()
        query.message = MagicMock()
        query.message.chat_id = 12345
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        mock_edit = AsyncMock()
        mock_edit.return_value = MagicMock(message_id=1)
        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(side_effect=Exception("boom")),
            ),
            patch("bot.handlers.userman_search.safe_edit_plain", new=mock_edit),
        ):
            result = await userman_search_action(update, context)
        assert result == WAITING_USERMAN_SEARCH
        # 2nd positional arg must be the real context object, not the error text
        assert mock_edit.call_args.args[1] is context
        assert isinstance(mock_edit.call_args.args[2], str)

    @pytest.mark.asyncio
    async def test_toggle_disabled_success(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_toggle_disabled"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch("bot.handlers.userman_search.run_blocking", new=AsyncMock()) as mock_block,
            patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()),
        ):
            result = await userman_search_action(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert mock_block.call_args_list[-1].args[0].__name__ == "disable_user"

    @pytest.mark.asyncio
    async def test_delete_success(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_delete"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch("bot.handlers.userman_search.run_blocking", new=AsyncMock()),
            patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()),
        ):
            result = await userman_search_action(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data.get("kick_um_idx") is None

    @pytest.mark.asyncio
    async def test_no_idx_ends(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_kick_execute"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
        ):
            result = await userman_search_action(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_execute_terminates_matching_sessions(self):

        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_kick_execute"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        sessions = [
            {"user": "ali", ".id": "*1"},
            {"user": "other", ".id": "*2"},
            {"user": "ali", ".id": "*3"},
        ]

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(side_effect=[sessions, None, None]),
            ) as mock_block,
            patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()),
        ):
            result = await userman_search_action(update, context)
        assert result == WAITING_USERMAN_SEARCH
        terminated_ids = [
            c.args[2]
            for c in mock_block.call_args_list
            if c.args[0].__name__ == "terminate_session"
        ]
        assert terminated_ids == ["*1", "*3"]

    @pytest.mark.asyncio
    async def test_reset_counters_success(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_reset_counters"
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ali", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch("bot.handlers.userman_search.run_blocking", new=AsyncMock()) as mock_block,
            patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()),
        ):
            result = await userman_search_action(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert mock_block.call_args_list[-1].args[0].__name__ == "reset_user_counters"


class TestUsermanSearchBack:
    @pytest.mark.asyncio
    async def test_back_from_detail(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "search_back"
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "x"}]
        context.user_data["kick_um_idx"] = 0

        with patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()):
            result = await userman_search_back(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert "kick_um_idx" not in context.user_data

    @pytest.mark.asyncio
    async def test_back_initial_no_nameerror(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "search_back"
        update.callback_query = query
        context = _ctx()

        with patch("bot.handlers.userman_search.edit_clean", new=AsyncMock()) as mock_edit:
            result = await userman_search_back(update, context)
        assert result == WAITING_USERMAN_SEARCH
        sent_text = mock_edit.call_args.args[2]
        assert sent_text == USERMAN_SEARCH_PROMPT


class TestUsermanSearchAddProfile:
    @pytest.mark.asyncio
    async def test_add_profile_shows_list(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_add_profile"
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ahmed", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        profiles = ["1M", "2M"]
        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=profiles),
            ),
            patch("bot.handlers.userman_search.safe_edit_plain", new=AsyncMock()) as mock_edit,
        ):
            result = await userman_search_add_profile(update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["add_profile_username"] == "ahmed"
        assert context.user_data["add_profile_list"] == profiles
        sent_text = mock_edit.call_args.args[2]
        from bot.messages import USERMAN_ADD_PROFILE_PROMPT

        assert sent_text == USERMAN_ADD_PROFILE_PROMPT

    @pytest.mark.asyncio
    async def test_add_profile_no_profiles(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_add_profile"
        update.callback_query = query
        context = _ctx()
        context.user_data["search_um_hosts"] = [{"name": "ahmed", "disabled": "true"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch("bot.handlers.userman_search.run_blocking", new=AsyncMock(return_value=[])),
            patch("bot.handlers.userman_search.safe_edit_plain", new=AsyncMock()) as mock_edit,
        ):
            result = await userman_search_add_profile(update, context)
        assert result == WAITING_USERMAN_SEARCH
        from bot.messages import USERMAN_NO_PROFILES_TO_ADD

        assert mock_edit.call_args.args[2] == USERMAN_NO_PROFILES_TO_ADD

    @pytest.mark.asyncio
    async def test_add_profile_selected_success(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_profile_1"
        update.callback_query = query
        context = _ctx()
        context.user_data["add_profile_username"] = "ahmed"
        context.user_data["add_profile_list"] = ["1M", "2M"]
        context.user_data["search_um_hosts"] = [{"name": "ahmed", "disabled": "false"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=(True, None)),
            ),
            patch("bot.handlers.userman_search.safe_edit_plain", new=AsyncMock()) as mock_edit,
        ):
            result = await userman_search_add_profile_selected(update, context)
        assert result == WAITING_USERMAN_SEARCH
        from bot.messages import USERMAN_ADD_PROFILE_SUCCESS

        assert mock_edit.call_args.args[2] == USERMAN_ADD_PROFILE_SUCCESS.format(
            profile="2M", username="ahmed"
        )
        assert "add_profile_username" not in context.user_data

    @pytest.mark.asyncio
    async def test_add_profile_selected_failure(self):
        update = _admin_update()
        query = MagicMock()
        query.answer = AsyncMock()
        query.data = "um_profile_0"
        update.callback_query = query
        context = _ctx()
        context.user_data["add_profile_username"] = "ahmed"
        context.user_data["add_profile_list"] = ["1M", "2M"]
        context.user_data["search_um_hosts"] = [{"name": "ahmed", "disabled": "true"}]
        context.user_data["kick_um_idx"] = 0

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=(False, "boom")),
            ),
            patch("bot.handlers.userman_search.safe_edit_plain", new=AsyncMock()) as mock_edit,
        ):
            result = await userman_search_add_profile_selected(update, context)
        assert result == WAITING_USERMAN_SEARCH
        from bot.messages import USERMAN_ADD_PROFILE_FAILED

        assert mock_edit.call_args.args[2] == USERMAN_ADD_PROFILE_FAILED.format(
            profile="1M", username="ahmed", error="boom"
        )


class TestUsermanSearchFlowE2E:
    """End-to-end simulation of the full search -> select -> add profile flow."""

    @pytest.mark.asyncio
    async def test_full_add_profile_flow(self):
        from bot.messages import (
            USERMAN_ADD_PROFILE_PROMPT,
            USERMAN_ADD_PROFILE_SUCCESS,
            USERMAN_SEARCH_PROMPT,
        )
        from utils import admin_decorator

        context = _ctx()
        context.user_data["search_um_hosts"] = []
        context.user_data["kick_um_idx"] = None

        blocked = {
            "edit_clean": AsyncMock(),
            "send_step": AsyncMock(),
            "safe_edit_plain": AsyncMock(),
        }
        profiles = ["1M", "2M"]

        # The @admin_only decorator enforces a 1s rate limit per user, so the
        # instant calls in this simulation must be cleared between steps.
        def _allow():
            admin_decorator._rate_limit_data.clear()

        # 1) Press "بحث عن مستخدم" button
        _allow()
        start_update = _admin_update()
        sq = MagicMock()
        sq.answer = AsyncMock()
        sq.data = "userman_search"
        start_update.callback_query = sq

        with patch("bot.handlers.userman_search.edit_clean", new=blocked["edit_clean"]):
            result = await userman_search_start(start_update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert blocked["edit_clean"].call_args.args[2] == USERMAN_SEARCH_PROMPT
        blocked["edit_clean"].reset_mock()

        # 2) Send a username to search
        _allow()
        query_update = _admin_update()
        msg = MagicMock()
        msg.text = "ali"
        query_update.message = msg

        loading = MagicMock()
        loading.message_id = 999
        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.send_loading",
                new=AsyncMock(return_value=loading),
            ),
            patch("bot.handlers.userman_search.delete_now", new=AsyncMock()),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(
                    return_value=[
                        {"name": "ali", "profile": "1M", "disabled": "false"},
                    ]
                ),
            ),
            patch("bot.handlers.userman_search.send_step", new=blocked["send_step"]),
        ):
            result = await userman_search_query(query_update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["search_um_hosts"]
        blocked["send_step"].reset_mock()

        # 3) Select the first result
        _allow()
        sel_update = _admin_update()
        selq = MagicMock()
        selq.answer = AsyncMock()
        selq.data = "um_sel_0"
        sel_update.callback_query = selq

        with patch("bot.handlers.userman_search.edit_clean", new=blocked["edit_clean"]):
            result = await userman_search_select(sel_update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["kick_um_idx"] == 0
        blocked["edit_clean"].reset_mock()

        # 4) Press "إضافة باقة"
        _allow()
        add_update = _admin_update()
        addq = MagicMock()
        addq.answer = AsyncMock()
        addq.data = "um_add_profile"
        add_update.callback_query = addq

        with (
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=profiles),
            ),
            patch(
                "bot.handlers.userman_search.safe_edit_plain",
                new=blocked["safe_edit_plain"],
            ),
        ):
            result = await userman_search_add_profile(add_update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert context.user_data["add_profile_username"] == "ali"
        assert context.user_data["add_profile_list"] == profiles
        assert blocked["safe_edit_plain"].call_args.args[2] == USERMAN_ADD_PROFILE_PROMPT
        blocked["safe_edit_plain"].reset_mock()

        # 5) Pick the second profile (index 1)
        _allow()
        pick_update = _admin_update()
        pickq = MagicMock()
        pickq.answer = AsyncMock()
        pickq.data = "um_profile_1"
        pick_update.callback_query = pickq

        with (
            patch("bot.handlers.userman_search.is_duplicate_callback", return_value=False),
            patch(
                "bot.handlers.userman_search.get_selected_router",
                return_value="discovered_1",
            ),
            patch(
                "bot.handlers.userman_search.run_blocking",
                new=AsyncMock(return_value=(True, None)),
            ),
            patch(
                "bot.handlers.userman_search.safe_edit_plain",
                new=blocked["safe_edit_plain"],
            ),
        ):
            result = await userman_search_add_profile_selected(pick_update, context)
        assert result == WAITING_USERMAN_SEARCH
        assert blocked["safe_edit_plain"].call_args.args[2] == USERMAN_ADD_PROFILE_SUCCESS.format(
            profile="2M", username="ali"
        )
        assert "add_profile_username" not in context.user_data
        assert "add_profile_list" not in context.user_data
