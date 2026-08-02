import logging
import sqlite3

from telegram import Message, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database.repositories.admin_roles import list_admin_roles, set_admin_role
from database.repositories.audit_logs import log_action
from utils.admin_decorator import ROLE_LABELS, ROLE_LEVELS, admin_only, require_role
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send
from utils.error_response import send_error

logger = logging.getLogger(__name__)

ROLE_SET_USAGE = "الاستخدام: /role <id> <admin|operator|viewer>"
ROLE_SET_INVALID = "الدور غير صالح. استخدم أحد القيم: admin, operator, viewer"
ROLE_SET_NOT_ADMIN = "المعرّف ليس ضمن المشرفين المسجّلين."
ROLE_SET_SELF_DEMOTE = "لا يمكنك خفض دورك الخاص عن الأدمن."
ROLE_SET_DONE = "✅ تم تعيين دور {label} للمشرف {admin_id}."

OP_ASSIGN_ROUTER_USAGE = "الاستخدام: /assign_router <operator_id> — ثم اختر الروترات"
OP_NO_ROUTERS = "⚠️ لا توجد روترات محفوظة لإسنادها."
OP_ASSIGN_SUCCESS = "✅ تم إسناد الراوتر #{router_id} للمشغّل {operator_id}"
OP_REVOKE_SUCCESS = "✅ تم سحب الراوتر #{router_id} من المشغّل {operator_id}"
OP_NO_ROUTERS_FOR_OP = "⚠️ لا توجد روترات مخصصة لك. تواصل مع المسؤول."


def _parse_role_target(msg: Message) -> tuple[int | None, str]:
    """Extract (target_id, new_role) from a message or forwarded message."""
    forward_user = getattr(msg, "forward_from", None)
    if forward_user:
        target = forward_user.id
        parts = (msg.text or "").split()
        new_role = parts[1].strip() if len(parts) >= 2 else ""
        return target, new_role
    if msg and msg.text:
        parts = msg.text.split()
        if len(parts) >= 3:
            try:
                return int(parts[1]), parts[2].strip()
            except ValueError:
                pass  # parse: non-numeric input — None return handles it
    return None, ""


CUSTOMER_ADD_USAGE = "الاستخدام: /add_customer <id>"
CUSTOMER_REMOVE_USAGE = "الاستخدام: /remove_customer <id>"
CUSTOMER_ADD_SUCCESS = "✅ تم إضافة العميل {customer_id} بنجاح."
CUSTOMER_REMOVE_SUCCESS = "✅ تم إزالة العميل {customer_id} بنجاح."


@admin_only
@require_role("admin")
async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List the current role of every registered admin."""
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    rows = list_admin_roles()
    lines = ["👥 أدوار المشرفين:\n"]
    for row in rows:
        label = ROLE_LABELS.get(row["role"], row["role"])
        lines.append(f"• {row['admin_id']}: {label}")
    lines.append("\nلتغيير الدور: " + ROLE_SET_USAGE)
    text = "\n".join(lines)

    if query:
        from bot.keyboards import get_main_keyboard

        await safe_edit_or_send(query, context, text, keyboard=get_main_keyboard())
    elif update.message:
        await update.message.reply_text(text)


@admin_only
@require_role("super_admin")
async def role_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super Admin assigns a role to an admin.

    Usage: /role <id> <role> or forward a message from the user.
    """
    msg = update.message
    if not msg:
        return
    target, new_role = _parse_role_target(msg)

    error = _validate_role_assignment(target, new_role, update)
    if error:
        await msg.reply_text(error)
        return
    assert target is not None and new_role is not None

    actor = update.effective_user.id if update.effective_user else 0
    try:
        set_admin_role(target, new_role, actor)
        log_action(
            "role_change",
            (update.effective_user.username if update.effective_user else "") or "",
            "",
            actor,
        )
    except sqlite3.Error as e:
        logger.error("role_set_command failed: %s", e)
        await send_error(update, context, e, log_extra="role_change")
        return
    label = ROLE_LABELS.get(new_role, new_role)
    logger.info("role_set_command: actor=%s set role=%s for target=%s", actor, new_role, target)
    await msg.reply_text(ROLE_SET_DONE.format(label=label, admin_id=target))


def _validate_role_assignment(
    target: int | None, new_role: str | None, update: Update,
) -> str | None:
    """Return an error message if the role assignment is invalid, else None."""
    if not target or not new_role:
        return ROLE_SET_USAGE + "\n💡 أو يمكنك تحويل (Forward) رسالة" \
            " المستخدم مع ملحق اسم الصلاحية (مثال: /role operator)."
    if new_role not in ROLE_LEVELS:
        return ROLE_SET_INVALID
    if target not in ADMIN_IDS:
        return ROLE_SET_NOT_ADMIN
    actor = update.effective_user.id if update.effective_user else 0
    if target == actor and new_role != "admin":
        logger.warning("role_set_command: self-demotion attempt by user=%s", actor)
        return ROLE_SET_SELF_DEMOTE
    return None


role_command = role_set_command


@admin_only
@require_role("super_admin")
async def add_customer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super Admin adds a new customer.

    Usage: /add_customer <id> or forward a message from the user.
    """
    target: int | None = None
    msg = update.message

    forward_user = getattr(msg, "forward_from", None)
    if msg and forward_user:
        target = forward_user.id
    elif msg and msg.text:
        parts = msg.text.split()
        if len(parts) >= 2:
            try:
                target = int(parts[1])
            except ValueError:
                pass  # parse: non-numeric input — handled by the falsy check below

    if not target or not msg:
        if msg:
            await msg.reply_text(
                CUSTOMER_ADD_USAGE + "\n💡 أو يمكنك ببساطة إعادة"
                " توجيه (Forward) أي رسالة من المستخدم للبوت."
            )
        return

    actor = update.effective_user.id if update.effective_user else 0
    try:
        set_admin_role(target, "customer", actor)
        username = (update.effective_user.username if update.effective_user else "") or ""
        log_action("add_customer", username, "", actor)
    except sqlite3.Error as e:
        logger.error("add_customer_command failed: %s", e)
        await send_error(update, context, e, log_extra="add_customer")
        return
    logger.info("add_customer_command: actor=%s added customer=%s", actor, target)
    await msg.reply_text(CUSTOMER_ADD_SUCCESS.format(customer_id=target))


@admin_only
@require_role("super_admin")
async def remove_customer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super Admin removes a customer: /remove_customer <id>."""
    from database.repositories.admin_roles import delete_admin_role

    parts = (update.message.text or "").split()
    if len(parts) < 2:
        await update.message.reply_text(CUSTOMER_REMOVE_USAGE)
        return

    try:
        target = int(parts[1])
    except ValueError:
        await update.message.reply_text("معرّف غير صالح.")
        return

    actor = update.effective_user.id
    try:
        delete_admin_role(target)
        log_action("remove_customer", update.effective_user.username or "", "", actor)
    except sqlite3.Error as e:
        logger.error("remove_customer_command failed: %s", e)
        await send_error(update, context, e, log_extra="remove_customer")
        return
    await update.message.reply_text(CUSTOMER_REMOVE_SUCCESS.format(customer_id=target))


@admin_only
@require_role("admin")
async def assign_router_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض واجهة إسناد الروترات لمشغّل معين.

    الاستخدام: /assign_router <operator_id>
    """
    from bot.keyboards import get_operator_router_assignment_keyboard
    from database.repositories.operator_permissions import get_operator_routers
    from database.repositories.routers import get_saved_routers

    parts = (update.message.text or "").split()
    if len(parts) < 2:
        await update.message.reply_text(OP_ASSIGN_ROUTER_USAGE)
        return

    try:
        operator_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ معرّف المشغّل يجب أن يكون رقماً صحيحاً.")
        return

    all_routers = get_saved_routers(active_only=True)
    if not all_routers:
        await update.message.reply_text(OP_NO_ROUTERS)
        return

    assigned = get_operator_routers(operator_id)
    keyboard = get_operator_router_assignment_keyboard(operator_id, all_routers, assigned)
    await update.message.reply_text(
        f"🛠️ إسناد الروترات للمشغّل <b>{operator_id}</b>\n"
        f"اضغط على راوتر لإسناده أو سحبه:\n"
        f"✅ = مُسنَد حالياً | ⬜ = غير مُسنَد",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@admin_only
@require_role("admin")
async def op_assign_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callback إسناد راوتر لمشغّل."""
    from bot.keyboards import get_operator_router_assignment_keyboard
    from database.repositories.operator_permissions import (
        assign_router_to_operator,
        get_operator_routers,
    )
    from database.repositories.routers import get_saved_routers
    from utils.callback_utils import safe_answer_callback

    query = update.callback_query
    await safe_answer_callback(query)

    parts = query.data.split(":")  # op_assign:<op_id>:<router_id>
    if len(parts) != 3:
        return
    try:
        operator_id = int(parts[1])
        router_id = int(parts[2])
    except ValueError:
        return

    actor = update.effective_user.id
    try:
        assign_router_to_operator(operator_id, router_id, actor)
    except sqlite3.Error as e:
        logger.error("op_assign_router_callback failed: %s", e)
        await send_error(update, context, e, log_extra="op_assign_router")
        return

    all_routers = get_saved_routers(active_only=True)
    assigned = get_operator_routers(operator_id)
    keyboard = get_operator_router_assignment_keyboard(operator_id, all_routers, assigned)
    await query.edit_message_reply_markup(reply_markup=keyboard)


@admin_only
@require_role("admin")
async def op_revoke_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callback سحب راوتر من مشغّل."""
    from bot.keyboards import get_operator_router_assignment_keyboard
    from database.repositories.operator_permissions import (
        get_operator_routers,
        revoke_router_from_operator,
    )
    from database.repositories.routers import get_saved_routers
    from utils.callback_utils import safe_answer_callback

    query = update.callback_query
    await safe_answer_callback(query)

    parts = query.data.split(":")  # op_revoke:<op_id>:<router_id>
    if len(parts) != 3:
        return
    try:
        operator_id = int(parts[1])
        router_id = int(parts[2])
    except ValueError:
        return

    try:
        revoke_router_from_operator(operator_id, router_id)
    except sqlite3.Error as e:
        logger.error("op_revoke_router_callback failed: %s", e)
        await send_error(update, context, e, log_extra="op_revoke_router")
        return

    all_routers = get_saved_routers(active_only=True)
    assigned = get_operator_routers(operator_id)
    keyboard = get_operator_router_assignment_keyboard(operator_id, all_routers, assigned)
    await query.edit_message_reply_markup(reply_markup=keyboard)
