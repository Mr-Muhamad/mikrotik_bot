"""Tests for bot/handlers/hotspot_edit.py — all handlers."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_EDIT_FIELD, WAITING_EDIT_VALUE
from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.hotspot_edit"


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
    stack.enter_context(patch(f"{P}.reply_final", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.edit_clean", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.cleanup_state"))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.set_current_action"))
    stack.enter_context(patch(f"{P}.get_selected_router", return_value="discovered_1"))
    stack.enter_context(patch(f"{P}.log_action"))
    stack.enter_context(patch(f"{P}.format_hotspot_user", return_value="TestUser"))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestHotspotEditStart:
    @pytest.mark.asyncio
    async def test_callback_path(self):
        update = make_mock_update(user_id=724730774, callback_data="edit")
        context = make_mock_context()
        from bot.handlers.hotspot_edit import hotspot_edit_start

        result = await hotspot_edit_start(update, context)
        assert result == WAITING_EDIT_FIELD

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = make_mock_update(user_id=724730774, text="/edit")
        context = make_mock_context()
        from bot.handlers.hotspot_edit import hotspot_edit_start

        result = await hotspot_edit_start(update, context)
        assert result == WAITING_EDIT_FIELD


class TestHotspotEditSearch:
    @pytest.mark.asyncio
    async def test_delegates_to_search(self):
        update = make_mock_update(user_id=724730774, text="testuser")
        context = make_mock_context()
        with patch(f"{P}.search_users_for_action", new_callable=AsyncMock, return_value=14):
            from bot.handlers.hotspot_edit import hotspot_edit_search

            result = await hotspot_edit_search(update, context)
        assert result == 14


class TestHotspotEditSelect:
    @pytest.mark.asyncio
    async def test_user_found(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_user_*1")
        context = make_mock_context()
        user_data = {"name": "testuser", "disabled": "no"}
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value=user_data,
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_select

            result = await hotspot_edit_select(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_user_999")
        context = make_mock_context()
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_select

            result = await hotspot_edit_select(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_user_1")
        context = make_mock_context()
        with patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_select

            result = await hotspot_edit_select(update, context)
        assert result == -1


class TestHotspotEditField:
    @pytest.mark.asyncio
    async def test_none_query_returns_wait(self):
        update = make_mock_update(user_id=724730774)
        update.callback_query = None
        context = make_mock_context()
        from bot.handlers.hotspot_edit import hotspot_edit_field

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_toggle_disabled_on(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_toggle_disabled")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}, current_field=""
        )
        from bot.handlers.hotspot_edit import hotspot_edit_field

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_toggle_disabled_off(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_toggle_disabled")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "yes"}, current_field=""
        )
        from bot.handlers.hotspot_edit import hotspot_edit_field

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_toggle_disabled_no_session(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_toggle_disabled")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="", user_data={}, current_field=""
        )
        with patch(f"{P}.get_selected_router", return_value=None):
            from bot.handlers.hotspot_edit import hotspot_edit_field

        result = await hotspot_edit_field(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_toggle_disabled_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_toggle_disabled")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}, current_field=""
        )
        with patch(
            f"{P}.hotspot_manager.edit_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_field

            result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_profile_field(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_profile")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}, current_field=""
        )
        with patch(
            f"{P}.fetch_and_cache_profiles",
            new_callable=AsyncMock,
            return_value=["default", "24h"],
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_field

            result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_profile_field_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_profile")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}, current_field=""
        )
        with patch(
            f"{P}.fetch_and_cache_profiles",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Profile fetch fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_field

            result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_name_field_shows_prompt(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_name")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}, current_field=""
        )
        from bot.handlers.hotspot_edit import hotspot_edit_field

        result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE
        assert context.user_data["hotspot_edit_session"].current_field == "name"

    @pytest.mark.asyncio
    async def test_bytes_field(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_field_bytes")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "testuser", "limit-bytes-total": "1000000"},
            current_field="",
        )
        with patch(f"{P}.format_bytes", return_value="1 MB"):
            from bot.handlers.hotspot_edit import hotspot_edit_field

            result = await hotspot_edit_field(update, context)
        assert result == WAITING_EDIT_VALUE


class TestHotspotEditValue:
    @pytest.mark.asyncio
    async def test_no_session_data_returns_end(self):
        update = make_mock_update(user_id=724730774, text="newname")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="", user_data={}, current_field=""
        )
        from bot.handlers.hotspot_edit import hotspot_edit_value

        result = await hotspot_edit_value(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_name_change_success(self):
        update = make_mock_update(user_id=724730774, text="newname")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "oldname", "disabled": "no"},
            current_field="name",
        )
        with (
            patch(f"{P}.validate_username", return_value=(True, "")),
            patch(f"{P}.hotspot_manager.user_exists", new_callable=AsyncMock, return_value=False),
            patch(f"{P}.hotspot_manager.kick_user", new_callable=AsyncMock, return_value=[]),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_name_invalid(self):
        update = make_mock_update(user_id=724730774, text="")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "old"}, current_field="name"
        )
        with patch(f"{P}.validate_username", return_value=(False, "Invalid name")):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_name_duplicate(self):
        update = make_mock_update(user_id=724730774, text="existing")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "old"}, current_field="name"
        )
        with (
            patch(f"{P}.validate_username", return_value=(True, "")),
            patch(f"{P}.hotspot_manager.user_exists", new_callable=AsyncMock, return_value=True),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_password_valid(self):
        update = make_mock_update(user_id=724730774, text="newpass123")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "u", "disabled": "no"}, current_field="password"
        )
        with patch(f"{P}.validate_password", return_value=(True, "")):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_password_invalid(self):
        update = make_mock_update(user_id=724730774, text="short")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "u"}, current_field="password"
        )
        with patch(f"{P}.validate_password", return_value=(False, "Too short")):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_bytes_valid(self):
        update = make_mock_update(user_id=724730774, text="100M")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "u", "disabled": "no"},
            current_field="bytes",
        )
        with patch(f"{P}.validate_bytes_input", return_value="100000000"):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_bytes_invalid(self):
        update = make_mock_update(user_id=724730774, text="xyz")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "u"}, current_field="bytes"
        )
        with patch(f"{P}.validate_bytes_input", side_effect=ValueError("Bad bytes")):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_renewal_day_valid(self):
        update = make_mock_update(user_id=724730774, text="15")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "u", "comment": "user/10", "disabled": "no"},
            current_field="renewal_day",
        )
        with patch(f"{P}._transform_renewal_day", return_value="u/15"):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_renewal_day_invalid(self):
        update = make_mock_update(user_id=724730774, text="99")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "u", "comment": ""},
            current_field="renewal_day",
        )
        with patch(f"{P}._transform_renewal_day", return_value=None):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_edit_exception(self):
        update = make_mock_update(user_id=724730774, text="ok")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "u", "disabled": "no"}, current_field="comment"
        )
        with patch(
            f"{P}.hotspot_manager.edit_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_bytes_field_triggers_kick(self):
        update = make_mock_update(user_id=724730774, text="50M")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "testuser", "disabled": "no"},
            current_field="bytes",
        )
        with (
            patch(f"{P}.validate_bytes_input", return_value="50000000"),
            patch(
                f"{P}.hotspot_manager.kick_user",
                new_callable=AsyncMock, return_value=["device1"],
            ),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_value

            result = await hotspot_edit_value(update, context)
        assert result == WAITING_EDIT_VALUE


class TestHotspotEditKick:
    @pytest.mark.asyncio
    async def test_kick_success(self):
        update = make_mock_update(user_id=724730774, callback_data="kick")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}
        )
        with patch(
            f"{P}.hotspot_manager.kick_user",
            new_callable=AsyncMock,
            return_value=["device1", "device2"],
        ), patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value={"name": "testuser", "disabled": "no"},
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_kick

            result = await hotspot_edit_kick(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_kick_no_active_devices(self):
        update = make_mock_update(user_id=724730774, callback_data="kick")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}
        )
        with patch(
            f"{P}.hotspot_manager.kick_user",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            f"{P}.hotspot_manager.get_user",
            new_callable=AsyncMock,
            return_value={"name": "testuser", "disabled": "no"},
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_kick

            result = await hotspot_edit_kick(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_kick_no_user_data(self):
        update = make_mock_update(user_id=724730774, callback_data="kick")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(user_id="*1", user_data={})
        from bot.handlers.hotspot_edit import hotspot_edit_kick

        result = await hotspot_edit_kick(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_kick_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="kick")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}
        )
        with patch(
            f"{P}.hotspot_manager.kick_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("kick fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_kick

            result = await hotspot_edit_kick(update, context)
        assert result == WAITING_EDIT_VALUE


class TestHotspotEditReset:
    @pytest.mark.asyncio
    async def test_reset_success(self):
        update = make_mock_update(user_id=724730774, callback_data="reset")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1",
            user_data={"name": "testuser", "disabled": "no"},
        )
        with (
            patch(
                f"{P}.hotspot_manager.reset_user_counters",
                new_callable=AsyncMock,
            ),
            patch(
                f"{P}.hotspot_manager.kick_user",
                new_callable=AsyncMock,
                return_value=["device1"],
            ),
            patch(
                f"{P}.hotspot_manager.get_user",
                new_callable=AsyncMock,
                return_value={"name": "testuser", "disabled": "no"},
            ),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_reset

            result = await hotspot_edit_reset(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_reset_no_active_devices(self):
        update = make_mock_update(user_id=724730774, callback_data="reset")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}
        )
        with (
            patch(f"{P}.hotspot_manager.reset_user_counters", new_callable=AsyncMock),
            patch(f"{P}.hotspot_manager.kick_user", new_callable=AsyncMock, return_value=[]),
            patch(
                f"{P}.hotspot_manager.get_user",
                new_callable=AsyncMock,
                return_value={"name": "testuser", "disabled": "no"},
            ),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_reset

            result = await hotspot_edit_reset(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_reset_no_session(self):
        update = make_mock_update(user_id=724730774, callback_data="reset")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="", user_data={}, current_field=""
        )
        from bot.handlers.hotspot_edit import hotspot_edit_reset

        result = await hotspot_edit_reset(update, context)
        assert result == -1

    @pytest.mark.asyncio
    async def test_reset_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="reset")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}
        )
        with patch(
            f"{P}.hotspot_manager.reset_user_counters",
            new_callable=AsyncMock,
            side_effect=RuntimeError("reset fail"),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_reset

            result = await hotspot_edit_reset(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_reset_disabled_user(self):
        update = make_mock_update(user_id=724730774, callback_data="reset")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "yes"}
        )
        with (
            patch(f"{P}.hotspot_manager.reset_user_counters", new_callable=AsyncMock),
            patch(f"{P}.hotspot_manager.kick_user", new_callable=AsyncMock, return_value=[]),
            patch(
                f"{P}.hotspot_manager.get_user",
                new_callable=AsyncMock,
                return_value={"name": "testuser", "disabled": "yes"},
            ),
        ):
            from bot.handlers.hotspot_edit import hotspot_edit_reset

            result = await hotspot_edit_reset(update, context)
        assert result == WAITING_EDIT_VALUE


class TestEditProfileSelected:
    @pytest.mark.asyncio
    async def test_profile_applied(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_profile_0")
        context = make_mock_context()
        context.user_data["profile_names"] = ["default", "24h"]
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}
        )
        from bot.handlers.hotspot_edit import edit_profile_selected

        result = await edit_profile_selected(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_profile_invalid(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_profile_99")
        context = make_mock_context()
        context.user_data["profile_names"] = ["default"]
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser"}
        )
        from bot.handlers.hotspot_edit import edit_profile_selected

        result = await edit_profile_selected(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_profile_exception(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_profile_0")
        context = make_mock_context()
        context.user_data["profile_names"] = ["default"]
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_id="*1", user_data={"name": "testuser", "disabled": "no"}
        )
        with patch(
            f"{P}.hotspot_manager.edit_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("profile fail"),
        ):
            from bot.handlers.hotspot_edit import edit_profile_selected

            result = await edit_profile_selected(update, context)
        assert result == WAITING_EDIT_VALUE


class TestEditBackToFields:
    @pytest.mark.asyncio
    async def test_with_user_data(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_back_to_fields")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(
            user_data={"name": "testuser", "disabled": "no"}
        )
        from bot.handlers.hotspot_edit import edit_back_to_fields

        result = await edit_back_to_fields(update, context)
        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_without_user_data(self):
        update = make_mock_update(user_id=724730774, callback_data="edit_back_to_fields")
        context = make_mock_context()
        context.user_data["hotspot_edit_session"] = MagicMock(user_data={})
        from bot.handlers.hotspot_edit import edit_back_to_fields

        result = await edit_back_to_fields(update, context)
        assert result == WAITING_EDIT_FIELD


class TestTransformRenewalDay:
    def test_valid_day(self):
        from bot.handlers.hotspot_edit import _transform_renewal_day

        result = _transform_renewal_day("15", {"name": "user1", "comment": ""})
        assert result == "user1/15"

    def test_invalid_day(self):
        from bot.handlers.hotspot_edit import _transform_renewal_day

        result = _transform_renewal_day("abc", {"name": "user1"})
        assert result is None

    def test_day_out_of_range(self):
        from bot.handlers.hotspot_edit import _transform_renewal_day

        result = _transform_renewal_day("32", {"name": "user1"})
        assert result is None

    def test_day_zero(self):
        from bot.handlers.hotspot_edit import _transform_renewal_day

        result = _transform_renewal_day("0", {"name": "user1"})
        assert result is None
