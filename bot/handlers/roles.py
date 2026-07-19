from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database.models import list_admin_roles, log_action, set_admin_role
from utils.admin_decorator import ROLE_LABELS, ROLE_LEVELS, admin_only, require_role

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

CUSTOMER_ADD_USAGE = "الاستخدام: /add_customer <id>"
CUSTOMER_REMOVE_USAGE = "الاستخدام: /remove_customer <id>"
CUSTOMER_ADD_SUCCESS = "✅ تم إضافة العميل {customer_id} بنجاح."
CUSTOMER_REMOVE_SUCCESS = "✅ تم إزالة العميل {customer_id} بنجاح."


@admin_only
@require_role("admin")
async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List the current role of every registered admin."""
    rows = list_admin_roles()
    lines = ["👥 أدوار المشرفين:\n"]
    for row in rows:
        label = ROLE_LABELS.get(row["role"], row["role"])
        lines.append(f"• {row['admin_id']}: {label}")
    lines.append("\nلتغيير الدور: " + ROLE_SET_USAGE)
    if update.message:
        await update.message.reply_text("\n".join(lines))


@admin_only
@require_role("admin")
async def role_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner/Admin sets the role of another admin: /role <id> <role>."""
    parts = (update.message.text or "").split()
    if len(parts) < 3:
        await update.message.reply_text(ROLE_SET_USAGE)
        return

    try:
        target = int(parts[1])
    except ValueError:
        await update.message.reply_text("معرّف غير صالح.")
        return

    new_role = parts[2].lower()
    if new_role not in ROLE_LEVELS:
        await update.message.reply_text(ROLE_SET_INVALID)
        return

    if target not in ADMIN_IDS:
        await update.message.reply_text(ROLE_SET_NOT_ADMIN)
        return

    actor = update.effective_user.id
    if target == actor and new_role != "admin":
        await update.message.reply_text(ROLE_SET_SELF_DEMOTE)
        return

    set_admin_role(target, new_role, actor)
    log_action(
        "role_change",
        update.effective_user.username or "",
        "",
        actor,
    )
    label = ROLE_LABELS.get(new_role, new_role)
    await update.message.reply_text(ROLE_SET_DONE.format(label=label, admin_id=target))


@admin_only
@require_role("super_admin")
async def add_customer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super Admin adds a new customer: /add_customer <id>."""
    parts = (update.message.text or "").split()
    if len(parts) < 2:
        await update.message.reply_text(CUSTOMER_ADD_USAGE)
        return

    try:
        target = int(parts[1])
    except ValueError:
        await update.message.reply_text("معرّف غير صالح.")
        return

    actor = update.effective_user.id
    set_admin_role(target, "customer", actor)
    log_action("add_customer", update.effective_user.username or "", "", actor)
    await update.message.reply_text(CUSTOMER_ADD_SUCCESS.format(customer_id=target))


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
    delete_admin_role(target)
    log_action("remove_customer", update.effective_user.username or "", "", actor)
    await update.message.reply_text(CUSTOMER_REMOVE_SUCCESS.format(customer_id=target))


@admin_only
@require_role("admin")
async def assign_router_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض واجهة إسناد الروترات لمشغّل معين.

    الاستخدام: /assign_router <operator_id>
    """
    from database.models import get_saved_routers, get_operator_routers
    from bot.keyboards import get_operator_router_assignment_keyboard

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
    keyboard = get_operator_router_assignment_keyboard(
        operator_id, all_routers, assigned
    )
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
    from database.models import (
        get_saved_routers,
        get_operator_routers,
        assign_router_to_operator,
    )
    from bot.keyboards import get_operator_router_assignment_keyboard
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
    assign_router_to_operator(operator_id, router_id, actor)

    # تحديث الـ keyboard
    all_routers = get_saved_routers(active_only=True)
    assigned = get_operator_routers(operator_id)
    keyboard = get_operator_router_assignment_keyboard(
        operator_id, all_routers, assigned
    )
    await query.edit_message_reply_markup(reply_markup=keyboard)


@admin_only
@require_role("admin")
async def op_revoke_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callback سحب راوتر من مشغّل."""
    from database.models import (
        get_saved_routers,
        get_operator_routers,
        revoke_router_from_operator,
    )
    from bot.keyboards import get_operator_router_assignment_keyboard
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

    revoke_router_from_operator(operator_id, router_id)

    # تحديث الـ keyboard
    all_routers = get_saved_routers(active_only=True)
    assigned = get_operator_routers(operator_id)
    keyboard = get_operator_router_assignment_keyboard(
        operator_id, all_routers, assigned
    )
    await query.edit_message_reply_markup(reply_markup=keyboard)
