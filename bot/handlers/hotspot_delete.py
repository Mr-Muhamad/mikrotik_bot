from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import get_cancel_keyboard, get_confirm_keyboard, get_hotspot_keyboard
from bot.messages import (
    CANCELLED,
    CONFIRM_DELETE,
    DELETE_USER_PROMPT,
    INCOMPLETE_DATA,
    SUCCESS_DELETE,
    USER_NOT_FOUND,
)
from bot.router_selector import cleanup_state, get_selected_router, nav_set, set_current_action
from core.hotspot_manager import hotspot_manager
from database.models import log_action
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback,is_duplicate_callback
from utils.chat_cleaner import delete_now, edit_clean, send_step
from utils.error_response import send_error
from .constants import WAITING_DELETE_ID, WAITING_INPUT
from .hotspot_common import search_users_for_action


@require_role("operator")
@admin_only
async def hotspot_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, DELETE_USER_PROMPT, get_cancel_keyboard())
    else:
        await send_step(update, context, DELETE_USER_PROMPT, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "hotspot_delete")
    nav_set(context, "menu_hotspot")
    return WAITING_DELETE_ID


@admin_only
async def hotspot_delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    user_id = query.data.replace("delete_user_", "")

    router_key = get_selected_router(query.from_user.id)
    try:
        user = await run_blocking(hotspot_manager.get_user, router_key, user_id)
        if not user:
            await query.edit_message_text(USER_NOT_FOUND)
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END

        context.user_data["delete_user_id"] = user_id
        await query.edit_message_text(
            CONFIRM_DELETE.format(hotspot_manager.format_user(user)),
            reply_markup=get_confirm_keyboard(),
        )
        return WAITING_INPUT
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="hotspot_delete_select",
            reply_markup=get_hotspot_keyboard(),
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END


@admin_only
async def hotspot_delete_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await search_users_for_action(update, context, "delete")


@admin_only
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if is_duplicate_callback(query.data, update.effective_user.id):
        return
    await safe_answer_callback(query)

    if query.data == "confirm_yes":
        router_key = get_selected_router(query.from_user.id)
        user_id = context.user_data.get("delete_user_id")

        if not router_key or not user_id:
            await query.edit_message_text(INCOMPLETE_DATA, reply_markup=get_hotspot_keyboard())
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END

        try:
            await run_blocking(hotspot_manager.delete_user, router_key, user_id)
            await run_blocking(log_action, "delete_user", user_id, router_key, query.from_user.id)
            await edit_clean(query, context, SUCCESS_DELETE, get_hotspot_keyboard())
        except Exception as e:
            await send_error(
                update, context, e, router_key=router_key,
                log_extra="confirm_callback",
                reply_markup=get_hotspot_keyboard(),
            )
    else:
        await query.edit_message_text(CANCELLED, reply_markup=get_hotspot_keyboard())

    cleanup_state(query.from_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
async def confirm_reprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-prompt the user when text is sent instead of pressing confirm/cancel buttons."""
    # حذف رسالة المستخدم النصية فقط — لا نحذف last_msg لأنه رسالة التأكيد التي تحمل الأزرار
    if update.message:
        await delete_now(context, update.effective_chat.id, update.message.message_id)
    return WAITING_INPUT
