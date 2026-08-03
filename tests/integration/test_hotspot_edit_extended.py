"""Extended tests for the Hotspot user edit flow — covers untested handlers.

Tests reset, kick, edit_profile_selected, edit_back_to_fields,
toggle_disabled, _transform_renewal_day, edit_search, and edge cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_EDIT_FIELD, WAITING_EDIT_VALUE
from bot.handlers.hotspot_edit import (
    _transform_renewal_day,  # type: ignore[reportPrivateUsage]
    edit_back_to_fields,
    edit_profile_selected,
    hotspot_edit_field,
    hotspot_edit_kick,
    hotspot_edit_reset,
    hotspot_edit_search,
    hotspot_edit_start,
    hotspot_edit_value,
)
from bot.handlers.session_models import get_hotspot_edit_session
from core.hotspot_manager import hotspot_manager
from database.models import save_user_session
from tests.fixtures.telegram_mocks import make_mock_update
from utils import admin_decorator

ADMIN_ID = 724730774
ROUTER_KEY = "discovered_1"


@pytest.fixture(autouse=True)
def _reset_rate_limit():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _seed_user(name="edit_user", uid_hint="*99"):  # type: ignore[reportMissingParameterType]
    hotspot_manager.add_user(ROUTER_KEY, name=name, password="1234", profile="default")
    users = hotspot_manager.search_users(ROUTER_KEY, name)
    return users[0] if users else None


def _setup_edit_session(context, user):  # type: ignore[reportMissingParameterType]
    session = get_hotspot_edit_session(context.user_data)
    session.user_id = str(user[".id"])
    session.user_data = dict(user)
    return session


# ── hotspot_edit_start ──────────────────────────────────────────────
class TestHotspotEditStartExtended:
    @pytest.mark.asyncio
    async def test_start_from_command(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="/edit")
        context = _make_context()

        result = await hotspot_edit_start(update, context)

        assert result == WAITING_EDIT_FIELD
        context.bot.send_message.assert_awaited_once()


# ── hotspot_edit_search ──────────────────────────────────────────────
class TestHotspotEditSearch:
    @pytest.mark.asyncio
    async def test_search_delegates_to_shared_logic(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(text="test_user")
        context = _make_context()

        with patch(
            "bot.handlers.hotspot_edit.search_users_for_action",
            new=AsyncMock(return_value=WAITING_EDIT_VALUE),
        ) as mock_search:
            result = await hotspot_edit_search(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_search.assert_awaited_once_with(update, context, "edit")


# ── hotspot_edit_reset ───────────────────────────────────────────────
class TestHotspotEditReset:
    @pytest.mark.asyncio
    async def test_reset_guard_no_session(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="reset_counters")
        context = _make_context()

        result = await hotspot_edit_reset(update, context)

        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_happy_path_with_kicked(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("resetme")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="reset_counters")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=[
                None,
                ["device1", "device2"],
                None,
                {"name": "resetme", ".id": user[".id"], "disabled": "no"},
            ]),
        ):
            result = await hotspot_edit_reset(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_no_active_devices(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("resetno")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="reset_counters")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=[
                None,
                [],
                None,
                {"name": "resetno", ".id": user[".id"], "disabled": "no"},
            ]),
        ):
            result = await hotspot_edit_reset(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_reset_exception(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("reseterr")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="reset_counters")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=Exception("api fail")),
        ):
            with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
                result = await hotspot_edit_reset(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_err.assert_awaited_once()


# ── hotspot_edit_kick ────────────────────────────────────────────────
class TestHotspotEditKick:
    @pytest.mark.asyncio
    async def test_kick_guard_no_user_data(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="kick_user")
        context = _make_context()

        result = await hotspot_edit_kick(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kick_happy_path_with_kicked(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("kickme")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="kick_user")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=[
                ["device1"],
                {"name": "kickme", ".id": user[".id"], "disabled": "no"},
            ]),
        ):
            result = await hotspot_edit_kick(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kick_no_active_devices(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("kicknone")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="kick_user")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=[
                [],
                {"name": "kicknone", ".id": user[".id"], "disabled": "no"},
            ]),
        ):
            result = await hotspot_edit_kick(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_kick_exception(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("kickerr")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="kick_user")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=Exception("kick fail")),
        ):
            with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
                result = await hotspot_edit_kick(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_err.assert_awaited_once()


# ── hotspot_edit_field: toggle_disabled ───────────────────────────────
class TestHotspotEditFieldToggle:
    @pytest.mark.asyncio
    async def test_toggle_guard_no_session(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        update = make_mock_update(callback_data="edit_field_toggle_disabled")
        context = _make_context()

        result = await hotspot_edit_field(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_toggle_happy_path(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("toggleme")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_field_toggle_disabled")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=[None, None]),
        ):
            result = await hotspot_edit_field(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_exception(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("toggleerr")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_field_toggle_disabled")

        with patch(
            "bot.handlers.hotspot_edit.run_blocking",
            new=AsyncMock(side_effect=Exception("toggle fail")),
        ):
            with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
                result = await hotspot_edit_field(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_err.assert_awaited_once()


# ── hotspot_edit_field: bytes formatting ──────────────────────────────
class TestHotspotEditFieldBytes:
    @pytest.mark.asyncio
    async def test_bytes_field_formats_value(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("bytesfmt")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.user_data["limit-bytes-total"] = "1000000000"

        update = make_mock_update(callback_data="edit_field_bytes")

        result = await hotspot_edit_field(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()


# ── hotspot_edit_field: generic field ─────────────────────────────────
class TestHotspotEditFieldGeneric:
    @pytest.mark.asyncio
    async def test_comment_field(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("commentf")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)
        session = get_hotspot_edit_session(context.user_data)
        session.user_data["comment"] = "test comment"

        update = make_mock_update(callback_data="edit_field_comment")

        result = await hotspot_edit_field(update, context)

        assert result == WAITING_EDIT_VALUE


# ── edit_profile_selected ─────────────────────────────────────────────
class TestEditProfileSelected:
    @pytest.mark.asyncio
    async def test_invalid_profile(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("profinv")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_profile_nonexistent")

        with patch(
            "bot.handlers.hotspot_edit.resolve_profile_from_callback",
            return_value=None,
        ):
            result = await edit_profile_selected(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("profok")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_profile_premium")

        with patch(
            "bot.handlers.hotspot_edit.resolve_profile_from_callback",
            return_value="premium",
        ):
            result = await edit_profile_selected(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("profexc")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_profile_premium")

        with patch(
            "bot.handlers.hotspot_edit.resolve_profile_from_callback",
            return_value="premium",
        ):
            with patch(
                "bot.handlers.hotspot_edit.run_blocking",
                new=AsyncMock(side_effect=Exception("api fail")),
            ):
                with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
                    result = await edit_profile_selected(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_err.assert_awaited_once()


# ── edit_back_to_fields ───────────────────────────────────────────────
class TestEditBackToFields:
    @pytest.mark.asyncio
    async def test_with_user_data(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("backf")
        assert user is not None
        context = _make_context()
        _setup_edit_session(context, user)

        update = make_mock_update(callback_data="edit_back_to_fields")

        result = await edit_back_to_fields(update, context)

        assert result == WAITING_EDIT_VALUE
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_user_data(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        context = _make_context()

        update = make_mock_update(callback_data="edit_back_to_fields")

        result = await edit_back_to_fields(update, context)

        assert result == WAITING_EDIT_FIELD


# ── hotspot_edit_value: renewal_day ───────────────────────────────────
class TestHotspotEditValueRenewalDay:
    @pytest.mark.asyncio
    async def test_renewal_day_valid(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("renewalok")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "renewal_day"

        update = make_mock_update(text="15")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_renewal_day_invalid(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("renewalbad")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "renewal_day"

        update = make_mock_update(text="abc")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_renewal_day_out_of_range(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("renewaloor")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "renewal_day"

        update = make_mock_update(text="32")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE


# ── _transform_renewal_day ───────────────────────────────────────────
class TestTransformRenewalDay:
    def test_invalid_non_digit(self):
        result = _transform_renewal_day("abc", {"comment": "", "name": "test"})
        assert result is None

    def test_out_of_range_zero(self):
        result = _transform_renewal_day("0", {"comment": "", "name": "test"})
        assert result is None

    def test_out_of_range_32(self):
        result = _transform_renewal_day("32", {"comment": "", "name": "test"})
        assert result is None

    def test_valid_day_with_existing_comment(self):
        result = _transform_renewal_day("15", {"comment": "olduser/10", "name": "olduser"})
        assert result == "olduser/15"

    def test_valid_day_without_comment(self):
        result = _transform_renewal_day("20", {"comment": "", "name": "myuser"})
        assert result == "myuser/20"

    def test_valid_day_no_name_fallback(self):
        result = _transform_renewal_day("5", {"comment": "", "name": ""})
        assert result == "user/5"


# ── hotspot_edit_value: name validation ───────────────────────────────
class TestHotspotEditValueNameValidation:
    @pytest.mark.asyncio
    async def test_invalid_username(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("nameinv")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "name"

        update = make_mock_update(text="")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_duplicate_username(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        hotspot_manager.add_user(ROUTER_KEY, name="existing", password="1234", profile="default")
        user = _seed_user("namedup")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "name"

        update = make_mock_update(text="existing")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_unchanged_username(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("nameunch")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "name"

        update = make_mock_update(text="nameunch")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_user_exists_api_error(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("nameerr")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "name"

        update = make_mock_update(text="newname")

        call_count = 0

        async def mock_run_blocking(func, *args, **kwargs):  # type: ignore[reportMissingParameterType]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from core.exceptions import RouterOSCommandError  # type: ignore[reportAttributeAccessIssue]
                raise RouterOSCommandError("timeout")
            return None

        with patch("bot.handlers.hotspot_edit.run_blocking", side_effect=mock_run_blocking):
            with patch("bot.handlers.hotspot_edit.send_error", new=AsyncMock()) as mock_err:
                result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE
        mock_err.assert_awaited_once()


# ── hotspot_edit_value: invalid password/bytes ────────────────────────
class TestHotspotEditValueInvalidInputs:
    @pytest.mark.asyncio
    async def test_invalid_password(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("pwdinv")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "password"

        update = make_mock_update(text="")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE

    @pytest.mark.asyncio
    async def test_invalid_bytes(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("bytesinv")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "bytes"

        update = make_mock_update(text="invalid_bytes")

        result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE


# ── hotspot_edit_value: bytes kick message ────────────────────────────
class TestHotspotEditBytesKick:
    @pytest.mark.asyncio
    async def test_bytes_update_with_kick(self, mock_mikrotik_api):  # type: ignore[reportMissingParameterType]
        save_user_session(ADMIN_ID, ROUTER_KEY)
        user = _seed_user("kickbytes")
        assert user is not None
        context = _make_context()
        session = _setup_edit_session(context, user)
        session.current_field = "bytes"

        update = make_mock_update(text="2G")

        call_count = 0

        async def mock_run_blocking(func, *args, **kwargs):  # type: ignore[reportMissingParameterType]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None
            elif call_count == 2:
                return ["device1", "device2"]
            return None

        with patch("bot.handlers.hotspot_edit.run_blocking", side_effect=mock_run_blocking):
            with patch("bot.handlers.hotspot_edit.log_action", new=AsyncMock()):
                result = await hotspot_edit_value(update, context)

        assert result == WAITING_EDIT_VALUE
