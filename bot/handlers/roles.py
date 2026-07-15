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
