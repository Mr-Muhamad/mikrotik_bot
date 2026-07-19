import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    get_cancel_keyboard,
    get_hotspot_keyboard,
    get_profile_keyboard,
    get_router_keyboard,
    get_skip_keyboard,
)
from bot.helpers.profiles import fetch_and_cache_profiles, PROFILE_SOURCE_HOTSPOT
from bot.messages import (
    HOTSPOT_ADD_BYTES_HINT,
    HOTSPOT_ADD_INVALID_UPTIME,
    HOTSPOT_ADD_USE_BUTTONS,
    ADD_USER_PROMPT,
    CHOOSE_PROFILE,
    CHOOSE_PROFILE_OR_TYPE,
    DUPLICATE_USER,
    ERROR_OCCURRED,
    INVALID_PROFILE,
    NO_ROUTER_SELECTED,
    SEND_BYTES_LIMIT,
    SEND_BYTES_LIMIT_SHORT,
    SEND_COMMENT,
    SEND_COMMENT_OR_SKIP,
    SEND_PASSWORD,
    SEND_UPTIME_TYPE,
    SUCCESS_ADD,
)
from bot.router_selector import (
    cleanup_state,
    get_selected_router,
    nav_set,
    set_current_action,
)
from bot.handlers.hotspot_flow_utils import (
    convert_uptime_value,
    get_uptime_type_keyboard,
    set_uptime_unit,
)
from bot.handlers.handler_utils import make_back_step, get_query_message
from bot.profile_callbacks import resolve_profile_from_callback
from utils.admin_decorator import admin_only, require_role
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import edit_clean, reply_final, schedule_delete, send_step
from utils.error_response import send_error
from utils.validators import validate_password, validate_username, validate_bytes_input
from .constants import (
    WAITING_BYTES_TOTAL,
    WAITING_COMMENT,
    WAITING_PASSWORD,
    WAITING_PROFILE,
    WAITING_USERNAME,
    WAITING_UPTIME_TYPE,
    WAITING_UPTIME_VALUE,
)
from .hotspot_common import execute_add_user
from .session_models import get_hotspot_add_session
from core.hotspot_manager import hotspot_manager
from utils.async_blocking import run_blocking

logger = logging.getLogger(__name__)


@require_role("operator")
@admin_only
async def hotspot_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, ADD_USER_PROMPT, get_cancel_keyboard())
    else:
        await send_step(update, context, ADD_USER_PROMPT, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "hotspot_add")
    nav_set(context, "menu_hotspot")
    return WAITING_USERNAME


@admin_only
async def hotspot_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    valid, msg = validate_username(username)
    if not valid:
        await send_step(update, context, f"❌ {msg}", get_cancel_keyboard())
        return WAITING_USERNAME

    router_key = get_selected_router(update.effective_user.id)
    if router_key:
        try:
            exists = await run_blocking(
                hotspot_manager.user_exists, router_key, username
            )
            if exists:
                await send_step(
                    update,
                    context,
                    DUPLICATE_USER + "\n\n" + ADD_USER_PROMPT,
                    get_cancel_keyboard(),
                )
                return WAITING_USERNAME
        except Exception as e:
            await send_error(
                update,
                context,
                e,
                router_key=router_key,
                log_extra="hotspot_add_username",
            )
            cleanup_state(update.effective_user.id, context.user_data)
            return ConversationHandler.END

    get_hotspot_add_session(context.user_data).username = username
    await send_step(
        update,
        context,
        SEND_PASSWORD,
        get_skip_keyboard("skip_password", "add_back_to_username"),
    )
    return WAITING_PASSWORD


@admin_only
async def hotspot_add_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    valid, msg = validate_password(password)
    if not valid:
        await send_step(
            update,
            context,
            f"❌ {msg}",
            get_skip_keyboard("skip_password", "add_back_to_username"),
        )
        return WAITING_PASSWORD
    get_hotspot_add_session(context.user_data).password = password
    router_key = get_selected_router(update.effective_user.id)
    try:
        profile_names = await fetch_and_cache_profiles(
            context,
            router_key,
            source=PROFILE_SOURCE_HOTSPOT,
        )
        await send_step(
            update,
            context,
            CHOOSE_PROFILE_OR_TYPE,
            get_profile_keyboard(profile_names, "add_profile", "add_back_to_password"),
        )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_add_password",
        )
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END
    return WAITING_PROFILE


@admin_only
async def hotspot_add_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = update.message.text.strip()
    get_hotspot_add_session(context.user_data).profile = profile
    await send_step(
        update,
        context,
        SEND_BYTES_LIMIT,
        get_skip_keyboard("skip_bytes", "add_back_to_profile"),
    )
    return WAITING_BYTES_TOTAL


@admin_only
async def hotspot_add_profile_selected(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await safe_answer_callback(query)
    profile = resolve_profile_from_callback(context, query.data, "add_profile_")
    if not profile:
        await query.edit_message_text(ERROR_OCCURRED.format(INVALID_PROFILE))
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    get_hotspot_add_session(context.user_data).profile = profile
    await query.edit_message_text(
        SEND_BYTES_LIMIT,
        reply_markup=get_skip_keyboard("skip_bytes", "add_back_to_profile"),
    )
    return WAITING_BYTES_TOTAL


@admin_only
async def hotspot_add_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bytes_input = update.message.text.strip()
    try:
        get_hotspot_add_session(context.user_data).bytes_total = validate_bytes_input(bytes_input)
    except ValueError as e:
        logger.warning(f"hotspot_add_bytes invalid input: {bytes_input}: {e}")
        await send_step(
            update,
            context,
            HOTSPOT_ADD_BYTES_HINT.format(error=e),
            get_skip_keyboard("skip_bytes", "add_back_to_profile"),
        )
        return WAITING_BYTES_TOTAL
    await send_step(
        update,
        context,
        SEND_UPTIME_TYPE,
        get_uptime_type_keyboard(),
    )
    return WAITING_UPTIME_TYPE


@admin_only
async def hotspot_add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text.strip()
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        await reply_final(update, context, NO_ROUTER_SELECTED, get_router_keyboard())
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    success, error = await execute_add_user(
        context, update.effective_user.id, router_key, comment
    )
    if success:
        await reply_final(update, context, SUCCESS_ADD, get_hotspot_keyboard())
    elif error == "duplicate":
        await send_step(
            update,
            context,
            DUPLICATE_USER + "\n\n" + ADD_USER_PROMPT,
            get_cancel_keyboard(),
        )
        return WAITING_USERNAME
    else:
        await reply_final(update, context, ERROR_OCCURRED.format(error))

    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END


add_back_to_username = make_back_step(
    ADD_USER_PROMPT, get_cancel_keyboard, WAITING_USERNAME
)
add_back_to_password = make_back_step(
    SEND_PASSWORD,
    lambda: get_skip_keyboard("skip_password", "add_back_to_username"),
    WAITING_PASSWORD,
)


@admin_only
async def add_back_to_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    try:
        profile_names = await fetch_and_cache_profiles(
            context,
            router_key,
            source=PROFILE_SOURCE_HOTSPOT,
        )
        await query.edit_message_text(
            CHOOSE_PROFILE_OR_TYPE,
            reply_markup=get_profile_keyboard(
                profile_names, "add_profile", "add_back_to_password"
            ),
        )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="add_back_to_profile",
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    return WAITING_PROFILE


add_back_to_bytes = make_back_step(
    SEND_BYTES_LIMIT_SHORT,
    lambda: get_skip_keyboard("skip_bytes", "add_back_to_profile"),
    WAITING_BYTES_TOTAL,
)
add_back_to_uptime_from_comment = make_back_step(
    SEND_UPTIME_TYPE, get_uptime_type_keyboard, WAITING_UPTIME_TYPE
)


@admin_only
async def skip_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    get_hotspot_add_session(context.user_data).password = ""
    router_key = get_selected_router(query.from_user.id)
    try:
        profile_names = await fetch_and_cache_profiles(
            context,
            router_key,
            source=PROFILE_SOURCE_HOTSPOT,
        )
        await query.edit_message_text(
            CHOOSE_PROFILE,
            reply_markup=get_profile_keyboard(
                profile_names, "add_profile", "add_back_to_password"
            ),
        )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="skip_password",
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    return WAITING_PROFILE


@admin_only
async def skip_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    get_hotspot_add_session(context.user_data).bytes_total = ""
    await query.edit_message_text(
        SEND_UPTIME_TYPE,
        reply_markup=get_uptime_type_keyboard(),
    )
    return WAITING_UPTIME_TYPE


@admin_only
async def hotspot_add_uptime_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    query_data = query.data

    if query_data == "uptime_hours":
        prompt, _ = set_uptime_unit(None, "uptime_unit", "hours")
        get_hotspot_add_session(context.user_data).uptime_type = "hours"
        await query.edit_message_text(
            prompt,
            reply_markup=get_skip_keyboard("skip_uptime", "add_back_to_bytes"),
        )
        return WAITING_UPTIME_VALUE
    elif query_data == "uptime_days":
        prompt, _ = set_uptime_unit(None, "uptime_unit", "days")
        get_hotspot_add_session(context.user_data).uptime_type = "days"
        await query.edit_message_text(
            prompt,
            reply_markup=get_skip_keyboard("skip_uptime", "add_back_to_bytes"),
        )
        return WAITING_UPTIME_VALUE
    elif query_data == "skip_uptime":
        get_hotspot_add_session(context.user_data).uptime_value = ""
        await query.edit_message_text(
            SEND_COMMENT_OR_SKIP,
            reply_markup=get_skip_keyboard("skip_comment", "add_back_to_uptime"),
        )
        return WAITING_COMMENT
    else:
        return WAITING_UPTIME_TYPE


@admin_only
async def hotspot_add_uptime_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    unit = get_hotspot_add_session(context.user_data).uptime_type or "hours"
    uptime = convert_uptime_value(value, unit)

    if not uptime:
        await send_step(
            update,
            context,
            HOTSPOT_ADD_INVALID_UPTIME,
            get_skip_keyboard("skip_uptime", "add_back_to_bytes"),
        )
        return WAITING_UPTIME_VALUE

    get_hotspot_add_session(context.user_data).uptime_value = str(uptime)
    await send_step(
        update,
        context,
        SEND_COMMENT_OR_SKIP,
        get_skip_keyboard("skip_comment", "add_back_to_uptime"),
    )
    return WAITING_COMMENT


@admin_only
async def skip_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    get_hotspot_add_session(context.user_data).uptime_value = ""
    await query.edit_message_text(
        SEND_COMMENT,
        reply_markup=get_skip_keyboard("skip_comment", "add_back_to_uptime"),
    )
    return WAITING_COMMENT


@admin_only
async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    if not router_key:
        await query.edit_message_text(
            NO_ROUTER_SELECTED, reply_markup=get_router_keyboard()
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    success, error = await execute_add_user(context, query.from_user.id, router_key, "")
    if success:
        await query.edit_message_text(SUCCESS_ADD, reply_markup=get_hotspot_keyboard())
        msg = get_query_message(query)
        if msg is not None:
            await schedule_delete(context, msg.chat_id, msg.message_id)
    elif error == "duplicate":
        await query.edit_message_text(
            DUPLICATE_USER + "\n\n" + ADD_USER_PROMPT,
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_USERNAME
    else:
        await query.edit_message_text(ERROR_OCCURRED.format(error))

    cleanup_state(query.from_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
async def hotspot_add_uptime_type_invalid_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle text input in WAITING_UPTIME_TYPE — tell user to use buttons."""
    await send_step(
        update,
        context,
        HOTSPOT_ADD_USE_BUTTONS,
        get_uptime_type_keyboard(),
    )
    return WAITING_UPTIME_TYPE


# Backward compatibility alias (used by bot.handlers.__init__ import)
add_back_to_uptime = add_back_to_uptime_from_comment
