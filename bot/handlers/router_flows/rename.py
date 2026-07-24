from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.constants import WAITING_RENAME
from bot.keyboards import get_router_keyboard, get_saved_routers_keyboard
from bot.messages import (
    ERROR_OCCURRED,
    ERROR_TRY_AGAIN,
    ROUTER_NAME_EMPTY,
    ROUTER_NOT_FOUND,
)
from bot.router_selector import cleanup_state, nav_set
from config import ROUTER_KEY_PREFIX
from core.mikrotik_api import mikrotik_api
from database.models import (
    get_router_by_id,
    get_router_display_name,
    get_saved_routers,
    log_action,
    update_router_alias,
)
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import is_duplicate_callback, safe_answer_callback
from utils.chat_cleaner import reply_final, send_step


@require_role("operator")
@admin_only
async def rename_router_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    if is_duplicate_callback(query):
        return ConversationHandler.END
    cleanup_state(query.from_user.id, context.user_data)
    nav_set(context, "saved_routers")
    try:
        router_id = int(query.data.replace("rename_router_", ""))
    except (ValueError, IndexError):
        await query.edit_message_text(ERROR_OCCURRED.format(""), reply_markup=get_router_keyboard())
        return ConversationHandler.END
    router = await run_blocking(get_router_by_id, router_id, decrypt=False)
    if not router:
        await query.edit_message_text(ROUTER_NOT_FOUND)
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data["rename_router_id"] = router_id
    current_name = get_router_display_name(router)
    await query.edit_message_text(f"✏️ أرسل الاسم الجديد للروتر:\n\nالاسم الحالي: {current_name}")
    return WAITING_RENAME


@admin_only
async def rename_router_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    router_id = context.user_data.get("rename_router_id")
    if not router_id:
        await reply_final(update, context, ERROR_TRY_AGAIN)
        context.user_data.clear()
        return ConversationHandler.END
    new_name = update.message.text.strip()
    if not new_name:
        await send_step(update, context, ROUTER_NAME_EMPTY)
        return WAITING_RENAME
    await run_blocking(update_router_alias, router_id, new_name)
    mikrotik_api.invalidate_router_name(f"{ROUTER_KEY_PREFIX}{router_id}")
    mikrotik_api.invalidate_version(f"{ROUTER_KEY_PREFIX}{router_id}")
    router = await run_blocking(get_router_by_id, router_id, decrypt=False)
    await run_blocking(
        log_action,
        "rename_router",
        new_name,
        router.get("identity", "") if router else "",
        update.effective_user.id,
    )
    await reply_final(
        update,
        context,
        f"✅ تم تغيير الاسم إلى: {new_name}",
        get_saved_routers_keyboard(await run_blocking(get_saved_routers, active_only=True)),
    )
    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END
