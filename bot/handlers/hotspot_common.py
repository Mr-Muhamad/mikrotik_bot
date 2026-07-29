import logging

from librouteros.exceptions import LibRouterosError
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    get_confirm_keyboard,
    get_edit_field_keyboard,
    get_paginated_user_keyboard,
    get_router_keyboard,
)
from bot.messages import (
    CONFIRM_DELETE,
    EDIT_SELECT_FIELD,
    HOTSPOT_PAGINATION_DELETE,
    HOTSPOT_PAGINATION_EDIT,
    NO_RESULTS,
    NO_ROUTER_SELECTED,
)
from bot.router_selector import cleanup_state, get_selected_router
from core.exceptions import MikrotikBotError
from core.hotspot_manager import hotspot_manager
from database.repositories.audit_logs import log_action
from utils.async_blocking import run_blocking
from utils.chat_cleaner import reply_final, send_step
from utils.error_response import send_error
from utils.formatters import format_hotspot_user
from utils.pagination import Paginator

from .constants import (
    WAITING_DELETE_ID,
    WAITING_DELETE_SELECT,
    WAITING_EDIT_FIELD,
    WAITING_EDIT_VALUE,
    WAITING_INPUT,
)
from .session_models import get_hotspot_add_session, get_hotspot_edit_session

logger = logging.getLogger(__name__)


async def search_users_for_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, action: str
) -> int:
    search_term = update.message.text
    router_key = get_selected_router(update.effective_user.id)

    if not router_key:
        await reply_final(update, context, NO_ROUTER_SELECTED, get_router_keyboard())
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    try:
        users = await run_blocking(hotspot_manager.search_users, router_key, search_term)
    except (LibRouterosError, OSError, MikrotikBotError) as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra=f"search_users({action})",
        )
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    if not users:
        await send_step(update, context, NO_RESULTS)
        return WAITING_DELETE_ID if action == "delete" else WAITING_EDIT_FIELD

    if len(users) == 1:
        user = users[0]
        if action == "delete":
            context.user_data.pop("users_cache", None)
            context.user_data["delete_user_id"] = user.get(".id", "")
            context.user_data["delete_user_name"] = user.get("name", "")
            await send_step(
                update,
                context,
                CONFIRM_DELETE.format(format_hotspot_user(user)),
                get_confirm_keyboard(),
            )
            return WAITING_INPUT
        context.user_data.pop("users_cache", None)
        edit_session = get_hotspot_edit_session(context.user_data)
        edit_session.user_id = str(user.get(".id", ""))
        edit_session.user_data = user
        await send_step(
            update,
            context,
            EDIT_SELECT_FIELD.format(format_hotspot_user(user)),
            get_edit_field_keyboard(),
        )
        return WAITING_EDIT_VALUE

    paginator = Paginator(users, page=0)
    context.user_data["users_cache"] = users

    if action == "delete":
        text = HOTSPOT_PAGINATION_DELETE.format(count=len(users), slice_info=paginator.slice_info)
        await send_step(
            update,
            context,
            text,
            get_paginated_user_keyboard(users, "delete_user", paginator),
        )
        return WAITING_DELETE_SELECT

    text = HOTSPOT_PAGINATION_EDIT.format(count=len(users), slice_info=paginator.slice_info)
    await send_step(
        update,
        context,
        text,
        get_paginated_user_keyboard(users, "edit_user", paginator),
    )
    return WAITING_EDIT_VALUE


async def execute_add_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    router_key: str,
    comment: str | None,
) -> tuple[bool, str | None]:
    session = get_hotspot_add_session(context.user_data)
    if not session.username:
        return False, "اسم المستخدم مطلوب"

    try:
        await run_blocking(
            hotspot_manager.add_user,
            router_key=router_key,
            name=session.username,
            password=session.password,
            profile=session.profile,
            bytes_total=session.bytes_total,
            uptime=session.uptime_value,
            comment=comment,
        )
        await run_blocking(
            log_action,
            "add_user",
            session.username,
            router_key,
            user_id,
        )
        return True, None
    except (LibRouterosError, OSError, MikrotikBotError) as e:
        logger.exception(f"execute_add_user failed: {e}")
        if "already have user" in str(e):
            context.user_data.pop("hotspot_add_session", None)
            return False, "duplicate"
        from utils.error_response import sanitize_error_text

        sanitized_err = sanitize_error_text(str(e))
        return False, sanitized_err


async def handle_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار التنقييم (page_edit_N / page_delete_N)."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_")
    if len(parts) < 4:
        return

    action = parts[1]  # "edit" or "delete"
    try:
        page = int(parts[3])
    except (ValueError, IndexError):
        return

    users = context.user_data.get("users_cache")
    if not users:
        return

    paginator = Paginator(users, page=page)

    if action == "edit":
        text = HOTSPOT_PAGINATION_EDIT.format(count=len(users), slice_info=paginator.slice_info)
        keyboard = get_paginated_user_keyboard(users, "edit_user", paginator)
        await query.edit_message_text(text, reply_markup=keyboard)
    elif action == "delete":
        text = HOTSPOT_PAGINATION_DELETE.format(count=len(users), slice_info=paginator.slice_info)
        keyboard = get_paginated_user_keyboard(users, "delete_user", paginator)
        await query.edit_message_text(text, reply_markup=keyboard)
