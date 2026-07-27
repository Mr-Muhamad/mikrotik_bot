import logging

from librouteros.exceptions import LibRouterosError
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.handler_utils import make_back_step
from bot.helpers.profiles import PROFILE_SOURCE_HOTSPOT, fetch_and_cache_profiles
from bot.keyboards import (
    get_back_keyboard,
    get_cancel_keyboard,
    get_edit_field_keyboard,
    get_profile_keyboard,
)
from bot.messages import (
    CHOOSE_NEW_PROFILE,
    DATA_ERROR,
    DUPLICATE_USER,
    EDIT_FIELD_NAMES,
    EDIT_SELECT_FIELD,
    EDIT_USER_PROMPT,
    ERROR_OCCURRED,
    HOTSPOT_EDIT_CURRENT_VALUE,
    HOTSPOT_EDIT_EMPTY_VALUE,
    HOTSPOT_EDIT_FIELD_PROMPT,
    HOTSPOT_EDIT_KICK_COUNT,
    HOTSPOT_EDIT_KICK_COUNT_INLINE,
    HOTSPOT_EDIT_RESET_SUCCESS,
    HOTSPOT_EDIT_SUCCESS,
    INVALID_PROFILE,
    NO_ACTIVE_DEVICES,
    NO_ACTIVE_DEVICES_FOR_USER,
    TOGGLE_DISABLED_OFF,
    TOGGLE_DISABLED_ON,
    USER_NOT_FOUND,
    USER_NOT_SELECTED,
)
from bot.profile_callbacks import resolve_profile_from_callback
from bot.router_selector import (
    cleanup_state,
    get_selected_router,
    nav_set,
    set_current_action,
)
from core.exceptions import MikrotikBotError
from core.hotspot_manager import hotspot_manager
from core.mikrotik_client import RouterOSRow
from database.models import log_action
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import edit_clean, reply_final, send_step
from utils.error_response import send_error
from utils.formatters import format_bytes, format_hotspot_user
from utils.validators import validate_bytes_input, validate_password, validate_username

from .constants import WAITING_EDIT_FIELD, WAITING_EDIT_VALUE
from .hotspot_common import search_users_for_action
from .session_models import get_hotspot_edit_session

logger = logging.getLogger(__name__)

FIELD_API_KEYS = {
    "name": "name",
    "password": "password",
    "profile": "profile",
    "bytes": "limit-bytes-total",
    "uptime": "limit-uptime",
    "comment": "comment",
    "renewal_day": "comment",
}


@require_role("operator")
@admin_only
async def hotspot_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the edit-user flow and prompt for a username search query.

    Args:
        update: Telegram update from callback or command.
        context: Conversation context; clears previous state.

    Returns:
        WAITING_EDIT_FIELD state.
    """
    cleanup_state(update.effective_user.id, context.user_data)
    context.args = []
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, EDIT_USER_PROMPT, get_cancel_keyboard())
    else:
        await send_step(update, context, EDIT_USER_PROMPT, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "hotspot_edit")
    nav_set(context, "menu_hotspot")
    return WAITING_EDIT_FIELD


@admin_only
async def hotspot_edit_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delegate text input to shared search logic for the edit flow.

    Args:
        update: Telegram update with message text query.
        context: Conversation context.

    Returns:
        Shared search handler return value (state constant).
    """
    return await search_users_for_action(update, context, "edit")


@admin_only
async def hotspot_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch selected hotspot user and display the field-edit keyboard.

    Args:
        update: Callback update with edit_user_<id> data.
        context: Conversation context; stores user data in session.

    Returns:
        WAITING_EDIT_VALUE or ConversationHandler.END on error.
    """
    query = update.callback_query
    await safe_answer_callback(query)

    user_id = query.data.replace("edit_user_", "")
    router_key = get_selected_router(query.from_user.id)
    try:
        user = await run_blocking(hotspot_manager.get_user, router_key, user_id)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "hotspot_edit_select failed "
            f"(error type: {type(e).__name__}): {e}"
        )
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_edit_select",
            reply_markup=get_cancel_keyboard(),
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    if not user:
        await query.edit_message_text(USER_NOT_FOUND)
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    get_hotspot_edit_session(context.user_data).user_id = user_id
    get_hotspot_edit_session(context.user_data).user_data = user

    is_disabled = str(user.get("disabled", "no")).lower() in ("yes", "true", "1")
    await query.edit_message_text(
        EDIT_SELECT_FIELD.format(format_hotspot_user(user)),
        reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
    )
    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset byte/uptime counters for the selected user and re-kick active sessions.

    Args:
        update: Callback update from the reset_counters button.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE state.
    """
    query = update.callback_query
    await safe_answer_callback(query)

    user_data = get_hotspot_edit_session(context.user_data).user_data
    user_id = get_hotspot_edit_session(context.user_data).user_id
    router_key = get_selected_router(query.from_user.id)

    if not router_key or not user_data or not user_id:
        await query.edit_message_text(USER_NOT_SELECTED)
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    try:
        logger.info("hotspot_edit_reset: user=%s on router=%s", user_id, router_key)
        await run_blocking(hotspot_manager.reset_user_counters, router_key, user_id)
        username = str(user_data.get("name", ""))
        kicked = await run_blocking(hotspot_manager.kick_user, router_key, username) or []
        await run_blocking(
            log_action,
            "reset_counters",
            f"user={username}",
            router_key,
            query.from_user.id,
        )

        fresh_user = await run_blocking(hotspot_manager.get_user, router_key, user_id)
        if fresh_user:
            get_hotspot_edit_session(context.user_data).user_data = fresh_user
            user_data = fresh_user

        is_disabled = str(user_data.get("disabled", "no")).lower() in (
            "yes",
            "true",
            "1",
        )
        if kicked:
            extra = HOTSPOT_EDIT_KICK_COUNT.format(count=len(kicked)) + "\n".join(
                f"• {n}" for n in kicked
            )
        else:
            extra = NO_ACTIVE_DEVICES

        text = (
            HOTSPOT_EDIT_RESET_SUCCESS
            + extra
            + "\n\n"
            + EDIT_SELECT_FIELD.format(format_hotspot_user(user_data))
        )
        await query.edit_message_text(
            text, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled)
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            "hotspot_edit_reset failed "
            f"(error type: {type(e).__name__}): {e}"
        )
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_edit_reset",
            reply_markup=get_edit_field_keyboard(),
        )
        return WAITING_EDIT_VALUE

    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick all active sessions for the selected hotspot user.

    Args:
        update: Callback update from the kick button.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE state.
    """
    query = update.callback_query
    await safe_answer_callback(query)

    user_data = get_hotspot_edit_session(context.user_data).user_data
    if not user_data:
        await query.edit_message_text(USER_NOT_SELECTED)
        return WAITING_EDIT_VALUE

    username = str(user_data.get("name", ""))
    router_key = get_selected_router(query.from_user.id)

    try:
        logger.info("hotspot_edit_kick: user=%s on router=%s", username, router_key)
        kicked = await run_blocking(hotspot_manager.kick_user, router_key, username) or []
        fresh_user = await run_blocking(
            hotspot_manager.get_user,
            router_key,
            get_hotspot_edit_session(context.user_data).user_id,
        )
        if fresh_user:
            get_hotspot_edit_session(context.user_data).user_data = fresh_user
        is_disabled = str((fresh_user or user_data).get("disabled", "no")).lower() in (
            "yes",
            "true",
            "1",
        )
        if kicked:
            msg = f"✅ تم طرد المستخدم من {len(kicked)} جهاز:\n" + "\n".join(
                f"• {n}" for n in kicked
            )
        else:
            msg = NO_ACTIVE_DEVICES_FOR_USER
        await query.edit_message_text(
            msg, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled)
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            "hotspot_edit_kick failed "
            f"(error type: {type(e).__name__}): {e}"
        )
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_edit_kick",
            reply_markup=get_edit_field_keyboard(),
        )

    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle field selection: toggle disabled, show profile picker, or prompt for value.

    Args:
        update: Callback update with edit_field_<name> data.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE or ConversationHandler.END.
    """
    query = update.callback_query
    await safe_answer_callback(query)

    if query is None or not query.data:
        return WAITING_EDIT_VALUE

    field = query.data.replace("edit_field_", "")
    get_hotspot_edit_session(context.user_data).current_field = field

    field_names = EDIT_FIELD_NAMES

    if field == "toggle_disabled":
        router_key = get_selected_router(query.from_user.id)
        user_id = get_hotspot_edit_session(context.user_data).user_id
        user_data = get_hotspot_edit_session(context.user_data).user_data
        if not router_key or not user_id or not user_data:
            await query.edit_message_text(USER_NOT_SELECTED)
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END

        current_disabled = str(user_data.get("disabled", "no")).lower() in (
            "yes",
            "true",
            "1",
        )
        new_disabled = not current_disabled
        new_value = "yes" if new_disabled else "no"

        try:
            await run_blocking(hotspot_manager.edit_user, router_key, user_id, disabled=new_value)
            await run_blocking(
                log_action, "toggle_disabled", user_id, router_key, query.from_user.id
            )

            user_data["disabled"] = new_value
            is_disabled = new_disabled
            toggle_msg = TOGGLE_DISABLED_OFF if new_disabled else TOGGLE_DISABLED_ON

            text = f"{toggle_msg}\n\n" + EDIT_SELECT_FIELD.format(format_hotspot_user(user_data))
            await query.edit_message_text(
                text, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled)
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "hotspot_edit_toggle_disabled failed "
                f"(error type: {type(e).__name__}): {e}"
            )
            await send_error(
                update,
                context,
                e,
                router_key=router_key,
                log_extra="hotspot_edit_toggle_disabled",
                reply_markup=get_edit_field_keyboard(),
            )
        return WAITING_EDIT_VALUE

    if field == "profile":
        router_key = get_selected_router(query.from_user.id)
        try:
            profile_names = await fetch_and_cache_profiles(
                context,
                router_key,
                source=PROFILE_SOURCE_HOTSPOT,
            )
            await edit_clean(
                query,
                context,
                CHOOSE_NEW_PROFILE,
                keyboard=get_profile_keyboard(profile_names, "edit_profile", "edit_back_to_fields"),
            )
            return WAITING_EDIT_VALUE
        except Exception as e:  # noqa: BLE001
            logger.error(
                "hotspot_edit_field failed "
                f"(error type: {type(e).__name__}): {e}"
            )
            await send_error(
                update,
                context,
                e,
                router_key=router_key,
                log_extra="hotspot_edit_field",
                reply_markup=get_edit_field_keyboard(),
            )
            return WAITING_EDIT_VALUE

    user_data = get_hotspot_edit_session(context.user_data).user_data
    api_key = str(FIELD_API_KEYS.get(field, field))
    current_value = user_data.get(api_key, HOTSPOT_EDIT_EMPTY_VALUE)
    if field == "bytes":
        current_value = format_bytes(current_value)

    await edit_clean(
        query,
        context,
        HOTSPOT_EDIT_FIELD_PROMPT.format(field_name=field_names.get(field, field))
        + HOTSPOT_EDIT_CURRENT_VALUE.format(current_value=current_value),
        keyboard=get_back_keyboard("edit_back_to_fields"),
    )
    return WAITING_EDIT_VALUE


@admin_only
async def edit_profile_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply the chosen profile to the hotspot user being edited.

    Args:
        update: Callback update with edit_profile_<name> data.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE state.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    profile = resolve_profile_from_callback(context, query.data, "edit_profile_")
    if not profile:
        await query.edit_message_text(ERROR_OCCURRED.format(INVALID_PROFILE))
        return WAITING_EDIT_VALUE
    router_key = get_selected_router(query.from_user.id)
    user_id = get_hotspot_edit_session(context.user_data).user_id
    try:
        await run_blocking(hotspot_manager.edit_user, router_key, user_id, profile=profile)
        await run_blocking(log_action, "edit_user", user_id, router_key, query.from_user.id)
        user_data = get_hotspot_edit_session(context.user_data).user_data
        if user_data:
            user_data["profile"] = profile
        is_disabled = str(user_data.get("disabled", "no")).lower() in (
            "yes",
            "true",
            "1",
        )
        await query.edit_message_text(
            EDIT_SELECT_FIELD.format(format_hotspot_user(user_data or {})),
            reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            "edit_profile_selected failed "
            f"(error type: {type(e).__name__}): {e}"
        )
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="edit_profile_selected",
            reply_markup=get_edit_field_keyboard(),
        )
    return WAITING_EDIT_VALUE


@admin_only
async def edit_back_to_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return from profile picker to the field-edit keyboard.

    Args:
        update: Callback update from the back button.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE or WAITING_EDIT_FIELD if no user selected.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    user_data = get_hotspot_edit_session(context.user_data).user_data
    if user_data:
        is_disabled = str(user_data.get("disabled", "no")).lower() in (
            "yes",
            "true",
            "1",
        )
        await query.edit_message_text(
            EDIT_SELECT_FIELD.format(format_hotspot_user(user_data)),
            reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
        )
    else:
        await query.edit_message_text(EDIT_USER_PROMPT, reply_markup=get_cancel_keyboard())
        return WAITING_EDIT_FIELD
    return WAITING_EDIT_VALUE


edit_back_search = make_back_step(EDIT_USER_PROMPT, get_cancel_keyboard, WAITING_EDIT_FIELD)


async def _validate_edit_field(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    api_field: str,
    field: str,
    new_value: str,
    router_key: str,
) -> str | None:
    """Validate *new_value* for the given field; return error message or ``None``."""
    if api_field == "name":
        valid, name_msg = validate_username(new_value)
        if not valid:
            await reply_final(update, context, f"❌ {name_msg}")
            return "stop"
        current_name = str(get_hotspot_edit_session(context.user_data).user_data.get("name", ""))
        if new_value != current_name:
            try:
                exists = await run_blocking(hotspot_manager.user_exists, router_key, new_value)
            except Exception as e:  # noqa: BLE001
                await send_error(
                    update,
                    context,
                    e,
                    router_key=router_key,
                    log_extra="hotspot_edit_value:user_exists",
                    reply_markup=get_back_keyboard("edit_back_to_fields"),
                )
                return "stop"
            if exists:
                await reply_final(update, context, DUPLICATE_USER)
                return "stop"
    elif api_field == "password":
        valid, pwd_msg = validate_password(new_value)
        if not valid:
            await reply_final(update, context, f"❌ {pwd_msg}")
            return "stop"
    elif api_field == "limit-bytes-total":
        try:
            new_value = validate_bytes_input(new_value)
        except ValueError as e:
            await reply_final(update, context, f"❌ {e}")
            return "stop"
    return new_value


def _transform_renewal_day(new_value: str, user_data: RouterOSRow) -> str | None:
    """Transform a renewal day input into ``name/day`` format, or ``None`` on error."""
    if not new_value.isdigit() or not (1 <= int(new_value) <= 31):
        return None
    day_num = int(new_value)
    current_comment = str(user_data.get("comment", "") or "")
    from core.hotspot_expiry import parse_renewal_day_from_comment

    clean_name, _ = parse_renewal_day_from_comment(current_comment)
    name_prefix = clean_name if clean_name else (str(user_data.get("name", "") or "") or "user")
    return f"{name_prefix}/{day_num}"


@admin_only
async def hotspot_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and apply the new value for the selected edit field.

    Args:
        update: Message update with the typed new value.
        context: Conversation context with active edit session.

    Returns:
        WAITING_EDIT_VALUE or ConversationHandler.END on error.
    """
    new_value = update.message.text.strip()
    session = get_hotspot_edit_session(context.user_data)
    field = session.current_field
    user_id = session.user_id
    router_key = get_selected_router(update.effective_user.id)

    if not router_key or not user_id or not field:
        await reply_final(update, context, DATA_ERROR)
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    api_field = str(FIELD_API_KEYS.get(field, field))

    result = await _validate_edit_field(update, context, api_field, field, new_value, router_key)
    if result == "stop":
        return WAITING_EDIT_VALUE
    if result is not None:
        new_value = result

    user_data = session.user_data
    if field == "renewal_day":
        transformed = _transform_renewal_day(new_value, user_data)
        if transformed is None:
            await reply_final(
                update,
                context,
                "❌ يرجى إدخال رقم يوم صالح بين 1 و 31" " (مثال: 15 أو 22)",
            )
            return WAITING_EDIT_VALUE
        new_value = transformed

    try:
        user_name = user_data.get("name", "") or user_id
        logger.info(
            "hotspot_edit_value: user=%s, field=%s on router=%s",
            user_id, field, router_key,
        )
        await run_blocking(hotspot_manager.edit_user, router_key, user_id, **{api_field: new_value})
        await run_blocking(log_action, "edit_user", user_id, router_key, update.effective_user.id)

        user_data[api_field] = new_value

        kick_msg = ""
        if field == "bytes" and user_name:
            kicked = await run_blocking(hotspot_manager.kick_user, router_key, user_name)
            if kicked:
                kick_msg = HOTSPOT_EDIT_KICK_COUNT_INLINE.format(count=len(kicked))

        is_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        text = HOTSPOT_EDIT_SUCCESS.format(kick_msg=kick_msg) + EDIT_SELECT_FIELD.format(
            format_hotspot_user(user_data)
        )
        await send_step(update, context, text, get_edit_field_keyboard(is_disabled=is_disabled))
        return WAITING_EDIT_VALUE
    except Exception as e:  # noqa: BLE001
        logger.error(
            "hotspot_edit_value failed "
            f"(error type: {type(e).__name__}): {e}"
        )
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_edit_value",
            reply_markup=get_back_keyboard("edit_back_to_fields"),
        )
        return WAITING_EDIT_VALUE
