"""Comprehensive tests for bot.handlers.roles — targeting 80%+ coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import roles as roles_module
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


@pytest.fixture(autouse=True)
def _bypass_decorators():
    """Unwrap @admin_only / @require_role so tests hit the real function body."""
    for attr in [
        "roles_command",
        "role_set_command",
        "add_customer_command",
        "remove_customer_command",
        "assign_router_command",
        "op_assign_router_callback",
        "op_revoke_router_callback",
    ]:
        if hasattr(roles_module, attr):
            original = getattr(roles_module, attr)
            while hasattr(original, "__wrapped__"):
                original = original.__wrapped__
            setattr(roles_module, attr, original)


def _msg_update(text: str, user_id: int = ADMIN_ID) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=user_id, username="testadmin")
    update.effective_chat = MagicMock(id=1, type="private")
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    msg.forward_from = None
    update.message = msg
    update.callback_query = None
    return update


def _callback_update(data: str, user_id: int = ADMIN_ID) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=user_id, username="testadmin")
    update.effective_chat = MagicMock(id=1, type="private")
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.data = data
    update.callback_query = query
    update.message = None
    return update


# ---------------------------------------------------------------------------
# _parse_role_target
# ---------------------------------------------------------------------------

class TestParseRoleTarget:
    def test_normal_text(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = "/role 123456 operator"
        target, role = roles_module._parse_role_target(msg)
        assert target == 123456
        assert role == "operator"

    def test_forwarded_message(self):
        msg = MagicMock()
        msg.forward_from = MagicMock(id=999999)
        msg.text = "/role admin"
        target, role = roles_module._parse_role_target(msg)
        assert target == 999999
        assert role == "admin"

    def test_forwarded_no_role(self):
        msg = MagicMock()
        msg.forward_from = MagicMock(id=111111)
        msg.text = "/role"
        target, role = roles_module._parse_role_target(msg)
        assert target == 111111
        assert role == ""

    def test_forwarded_no_text(self):
        msg = MagicMock()
        msg.forward_from = MagicMock(id=222222)
        msg.text = None
        target, role = roles_module._parse_role_target(msg)
        assert target == 222222
        assert role == ""

    def test_no_text(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = None
        target, role = roles_module._parse_role_target(msg)
        assert target is None
        assert role == ""

    def test_empty_text(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = ""
        target, role = roles_module._parse_role_target(msg)
        assert target is None
        assert role == ""

    def test_invalid_target_id(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = "/role abc operator"
        target, role = roles_module._parse_role_target(msg)
        assert target is None
        assert role == ""

    def test_only_two_parts(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = "/role 123456"
        target, role = roles_module._parse_role_target(msg)
        assert target is None
        assert role == ""

    def test_none_msg(self):
        target, role = roles_module._parse_role_target(None)
        assert target is None
        assert role == ""

    def test_extra_parts(self):
        msg = MagicMock()
        msg.forward_from = None
        msg.text = "/role 123456 viewer extra"
        target, role = roles_module._parse_role_target(msg)
        assert target == 123456
        assert role == "viewer"


# ---------------------------------------------------------------------------
# roles_command
# ---------------------------------------------------------------------------

class TestRolesCommand:
    @pytest.mark.asyncio
    async def test_callback_path(self):
        update = _callback_update("roles_list")
        ctx = MagicMock()

        with (
            patch("bot.handlers.roles.list_admin_roles", return_value=[
                {"admin_id": 111, "role": "admin"},
                {"admin_id": 222, "role": "operator"},
            ]),
            patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.roles.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
            patch("bot.keyboards.get_main_keyboard", return_value="KB"),
        ):
            await roles_module.roles_command(update, ctx)
            mock_edit.assert_called_once()
            call_text = mock_edit.call_args[0][2]
            assert "111" in call_text
            assert "222" in call_text

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = _msg_update("/roles")
        ctx = MagicMock()

        with (
            patch("bot.handlers.roles.list_admin_roles", return_value=[
                {"admin_id": 111, "role": "viewer"},
            ]),
        ):
            await roles_module.roles_command(update, ctx)
            update.message.reply_text.assert_called_once()
            text = update.message.reply_text.call_args[0][0]
            assert "111" in text

    @pytest.mark.asyncio
    async def test_empty_roles_callback(self):
        update = _callback_update("roles_list")
        ctx = MagicMock()

        with (
            patch("bot.handlers.roles.list_admin_roles", return_value=[]),
            patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.roles.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
            patch("bot.keyboards.get_main_keyboard", return_value="KB"),
        ):
            await roles_module.roles_command(update, ctx)
            mock_edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_roles_message(self):
        update = _msg_update("/roles")
        ctx = MagicMock()

        with patch("bot.handlers.roles.list_admin_roles", return_value=[]):
            await roles_module.roles_command(update, ctx)
            update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# role_set_command
# ---------------------------------------------------------------------------

class TestRoleSetCommand:
    @pytest.mark.asyncio
    async def test_missing_target_and_role(self):
        update = _msg_update("/role")
        ctx = MagicMock()
        await roles_module.role_set_command(update, ctx)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text

    @pytest.mark.asyncio
    async def test_invalid_role(self):
        update = _msg_update("/role 123456 hacker")
        ctx = MagicMock()
        await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الدور غير صالح" in text

    @pytest.mark.asyncio
    async def test_not_in_admin_ids(self):
        update = _msg_update("/role 999999 operator")
        ctx = MagicMock()
        with patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID]):
            await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "ليس ضمن المشرفين" in text

    @pytest.mark.asyncio
    async def test_self_demotion(self):
        update = _msg_update(f"/role {ADMIN_ID} operator")
        ctx = MagicMock()
        with patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID]):
            await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "لا يمكنك خفض" in text

    @pytest.mark.asyncio
    async def test_self_to_admin_ok(self):
        update = _msg_update(f"/role {ADMIN_ID} admin")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID]),
            patch("bot.handlers.roles.set_admin_role"),
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "تم تعيين دور" in text

    @pytest.mark.asyncio
    async def test_success(self):
        update = _msg_update("/role 555555 operator")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID, 555555]),
            patch("bot.handlers.roles.set_admin_role") as mock_set,
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.role_set_command(update, ctx)
        mock_set.assert_called_once_with(555555, "operator", ADMIN_ID)
        text = update.message.reply_text.call_args[0][0]
        assert "تم تعيين دور" in text

    @pytest.mark.asyncio
    async def test_forwarded_message(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID, username="admin")
        update.effective_chat = MagicMock(id=1, type="private")
        update.message = MagicMock()
        update.message.forward_from = MagicMock(id=888888)
        update.message.text = "/role operator"
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        with (
            patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID, 888888]),
            patch("bot.handlers.roles.set_admin_role") as mock_set,
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.role_set_command(update, MagicMock())
        mock_set.assert_called_once_with(888888, "operator", ADMIN_ID)

    @pytest.mark.asyncio
    async def test_no_message_path(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID, username="admin")
        update.effective_chat = MagicMock(id=1, type="private")
        update.message = MagicMock()
        update.message.forward_from = None
        update.message.text = None
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        ctx = MagicMock()
        with patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID]):
            await roles_module.role_set_command(update, ctx)

    @pytest.mark.asyncio
    async def test_role_viewer(self):
        update = _msg_update("/role 555555 viewer")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.ADMIN_IDS", [ADMIN_ID, 555555]),
            patch("bot.handlers.roles.set_admin_role"),
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "تم تعيين دور" in text

    @pytest.mark.asyncio
    async def test_missing_role_part(self):
        update = _msg_update("/role 555555")
        ctx = MagicMock()
        await roles_module.role_set_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text


# ---------------------------------------------------------------------------
# add_customer_command
# ---------------------------------------------------------------------------

class TestAddCustomerCommand:
    @pytest.mark.asyncio
    async def test_missing_target(self):
        update = _msg_update("/add_customer")
        ctx = MagicMock()
        await roles_module.add_customer_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        update = _msg_update("/add_customer abc")
        ctx = MagicMock()
        await roles_module.add_customer_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text

    @pytest.mark.asyncio
    async def test_success(self):
        update = _msg_update("/add_customer 333333")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.set_admin_role") as mock_set,
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.add_customer_command(update, ctx)
        mock_set.assert_called_once_with(333333, "customer", ADMIN_ID)
        text = update.message.reply_text.call_args[0][0]
        assert "تم إضافة العميل" in text

    @pytest.mark.asyncio
    async def test_forwarded_message(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID, username="admin")
        update.effective_chat = MagicMock(id=1, type="private")
        update.message = MagicMock()
        update.message.forward_from = MagicMock(id=444444)
        update.message.text = "/add_customer"
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        with (
            patch("bot.handlers.roles.set_admin_role") as mock_set,
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.add_customer_command(update, MagicMock())
        mock_set.assert_called_once_with(444444, "customer", ADMIN_ID)

    @pytest.mark.asyncio
    async def test_no_message(self):
        update = MagicMock()
        update.effective_user = MagicMock(id=ADMIN_ID, username="admin")
        update.effective_chat = MagicMock(id=1, type="private")
        update.message = MagicMock()
        update.message.forward_from = None
        update.message.text = None
        update.message.reply_text = AsyncMock()
        update.callback_query = None

        await roles_module.add_customer_command(update, MagicMock())


# ---------------------------------------------------------------------------
# remove_customer_command
# ---------------------------------------------------------------------------

class TestRemoveCustomerCommand:
    @pytest.mark.asyncio
    async def test_missing_parts(self):
        update = _msg_update("/remove_customer")
        ctx = MagicMock()
        await roles_module.remove_customer_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        update = _msg_update("/remove_customer abc")
        ctx = MagicMock()
        await roles_module.remove_customer_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "معرّف غير صالح" in text

    @pytest.mark.asyncio
    async def test_success(self):
        update = _msg_update("/remove_customer 333333")
        ctx = MagicMock()
        with (
            patch("database.repositories.admin_roles.delete_admin_role") as mock_del,
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.remove_customer_command(update, ctx)
        mock_del.assert_called_once_with(333333)
        text = update.message.reply_text.call_args[0][0]
        assert "تم إزالة العميل" in text

    @pytest.mark.asyncio
    async def test_valid_numeric_id(self):
        update = _msg_update("/remove_customer 999")
        ctx = MagicMock()
        with (
            patch("database.repositories.admin_roles.delete_admin_role"),
            patch("bot.handlers.roles.log_action"),
        ):
            await roles_module.remove_customer_command(update, ctx)
        assert update.message.reply_text.call_args[0][0]


# ---------------------------------------------------------------------------
# assign_router_command
# ---------------------------------------------------------------------------

class TestAssignRouterCommand:
    @pytest.mark.asyncio
    async def test_no_operator_id(self):
        update = _msg_update("/assign_router")
        ctx = MagicMock()
        await roles_module.assign_router_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "الاستخدام" in text

    @pytest.mark.asyncio
    async def test_invalid_operator_id(self):
        update = _msg_update("/assign_router abc")
        ctx = MagicMock()
        await roles_module.assign_router_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "رقماً صحيحاً" in text

    @pytest.mark.asyncio
    async def test_no_routers(self):
        update = _msg_update("/assign_router 123")
        ctx = MagicMock()
        # الوحدة تستورد مباشرة من database.repositories.routers وليس من database.models
        with patch("database.repositories.routers.get_saved_routers", return_value=[]):
            await roles_module.assign_router_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "لا توجد روترات" in text

    @pytest.mark.asyncio
    async def test_success(self):
        update = _msg_update("/assign_router 123")
        ctx = MagicMock()
        routers = [{"id": 1, "name": "r1"}]
        with (
            # تحديد مسار الاستيراد الفعلي: lazy import داخل الدالة من repositories
            patch("database.repositories.routers.get_saved_routers", return_value=routers),
            patch("database.repositories.operator_permissions.get_operator_routers", return_value=[1]),
            patch(
                "bot.keyboards.get_operator_router_assignment_keyboard",
                return_value="KB",
            ),
        ):
            await roles_module.assign_router_command(update, ctx)
        update.message.reply_text.assert_called_once()
        kwargs = update.message.reply_text.call_args[1]
        assert kwargs["reply_markup"] == "KB"
        assert kwargs["parse_mode"] == "HTML"


# ---------------------------------------------------------------------------
# op_assign_router_callback
# ---------------------------------------------------------------------------

class TestOpAssignRouterCallback:
    @pytest.mark.asyncio
    async def test_invalid_parts_too_few(self):
        update = _callback_update("op_assign:123")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_assign_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_operator_id(self):
        update = _callback_update("op_assign:abc:456")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_assign_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_router_id(self):
        update = _callback_update("op_assign:123:xyz")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_assign_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_success(self):
        update = _callback_update("op_assign:123:456")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock),
            patch(
                "database.repositories.operator_permissions.assign_router_to_operator"
            ) as mock_assign,
            patch("database.models.get_saved_routers", return_value=[{"id": 456}]),
            patch("database.models.get_operator_routers", return_value=[456]),
            patch(
                "bot.keyboards.get_operator_router_assignment_keyboard",
                return_value="KB",
            ),
        ):
            await roles_module.op_assign_router_callback(update, ctx)
        mock_assign.assert_called_once_with(123, 456, ADMIN_ID)
        update.callback_query.edit_message_reply_markup.assert_called_once_with(
            reply_markup="KB"
        )

    @pytest.mark.asyncio
    async def test_extra_parts(self):
        update = _callback_update("op_assign:123:456:789")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_assign_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()


# ---------------------------------------------------------------------------
# op_revoke_router_callback
# ---------------------------------------------------------------------------

class TestOpRevokeRouterCallback:
    @pytest.mark.asyncio
    async def test_invalid_parts_too_few(self):
        update = _callback_update("op_revoke:123")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_revoke_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_operator_id(self):
        update = _callback_update("op_revoke:abc:456")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_revoke_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_router_id(self):
        update = _callback_update("op_revoke:123:xyz")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_revoke_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_success(self):
        update = _callback_update("op_revoke:123:456")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock),
            patch(
                "database.repositories.operator_permissions.revoke_router_from_operator"
            ) as mock_revoke,
            patch("database.models.get_saved_routers", return_value=[{"id": 999}]),
            patch("database.models.get_operator_routers", return_value=[]),
            patch(
                "bot.keyboards.get_operator_router_assignment_keyboard",
                return_value="KB",
            ),
        ):
            await roles_module.op_revoke_router_callback(update, ctx)
        mock_revoke.assert_called_once_with(123, 456)
        update.callback_query.edit_message_reply_markup.assert_called_once_with(
            reply_markup="KB"
        )

    @pytest.mark.asyncio
    async def test_extra_parts(self):
        update = _callback_update("op_revoke:123:456:789")
        ctx = MagicMock()
        with patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock):
            await roles_module.op_revoke_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_not_called()

    @pytest.mark.asyncio
    async def test_only_two_parts(self):
        update = _callback_update("op_revoke:123:456")
        ctx = MagicMock()
        with (
            patch("bot.handlers.roles.safe_answer_callback", new_callable=AsyncMock),
            patch(
                "database.repositories.operator_permissions.revoke_router_from_operator"
            ),
            patch("database.models.get_saved_routers", return_value=[]),
            patch("database.models.get_operator_routers", return_value=[]),
            patch(
                "bot.keyboards.get_operator_router_assignment_keyboard",
                return_value="KB",
            ),
        ):
            await roles_module.op_revoke_router_callback(update, ctx)
        update.callback_query.edit_message_reply_markup.assert_called_once()
