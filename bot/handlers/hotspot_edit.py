from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

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
    INVALID_PROFILE,
    NO_ACTIVE_DEVICES,
    NO_ACTIVE_DEVICES_FOR_USER,
    TOGGLE_DISABLED_OFF,
    TOGGLE_DISABLED_ON,
    USER_NOT_FOUND,
    USER_NOT_SELECTED,
)
from bot.router_selector import cleanup_state, get_selected_router, nav_set, set_current_action
from bot.helpers.profiles import fetch_and_cache_profiles, PROFILE_SOURCE_HOTSPOT
from core.hotspot_manager import hotspot_manager
from database.models import log_action
from bot.profile_callbacks import resolve_profile_from_callback
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import edit_clean, reply_final, send_step
from utils.error_response import send_error
from utils.formatters import format_bytes
from utils.validators import validate_username,validate_bytes_input
from .constants import WAITING_EDIT_FIELD, WAITING_EDIT_VALUE
from .hotspot_common import search_users_for_action

FIELD_API_KEYS = {
    "name": "name",
    "password": "password",
    "profile": "profile",
    "bytes": "limit-bytes-total",
    "uptime": "limit-uptime",
    "comment": "comment",
}


@require_role("operator")
@admin_only
async def hotspot_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
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
    return await search_users_for_action(update, context, "edit")


@admin_only
async def hotspot_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    user_id = query.data.replace("edit_user_", "")
    router_key = get_selected_router(query.from_user.id)
    try:
        user = await run_blocking(hotspot_manager.get_user, router_key, user_id)
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="hotspot_edit_select",
            reply_markup=get_cancel_keyboard(),
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    if not user:
        await query.edit_message_text(USER_NOT_FOUND)
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    context.user_data["edit_user_id"] = user_id
    context.user_data["edit_user_data"] = user

    is_disabled = str(user.get("disabled", "no")).lower() in ("yes", "true", "1")
    await query.edit_message_text(
        EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user)),
        reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
    )
    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    user_data = context.user_data.get("edit_user_data")
    user_id = context.user_data.get("edit_user_id")
    router_key = get_selected_router(query.from_user.id)

    if not router_key or user_data is None or not user_id:
        await query.edit_message_text(USER_NOT_SELECTED)
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    try:
        await run_blocking(hotspot_manager.reset_user_counters, router_key, user_id)
        username = str(user_data.get("name", ""))
        kicked = await run_blocking(hotspot_manager.kick_user, router_key, username) or []
        await run_blocking(log_action, "reset_counters", f"user={username}", router_key, query.from_user.id)
        
        fresh_user = await run_blocking(hotspot_manager.get_user, router_key, user_id)
        if fresh_user:
            context.user_data["edit_user_data"] = fresh_user
            user_data = fresh_user

        is_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        if kicked:
            extra = f"🔄 تم طرد المستخدم من {len(kicked)} جهاز:\n" + "\n".join(f"• {n}" for n in kicked)
        else:
            extra = NO_ACTIVE_DEVICES

        text = (
            "✅ تم تصفير العدادات\n" + extra + "\n\n"
            + EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user_data))
        )
        await query.edit_message_text(text, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled))
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="hotspot_edit_reset",
            reply_markup=get_edit_field_keyboard(),
        )
        return WAITING_EDIT_VALUE

    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    user_data = context.user_data.get("edit_user_data")
    if not user_data:
        await query.edit_message_text(USER_NOT_SELECTED)
        return WAITING_EDIT_VALUE

    username = str(user_data.get("name", ""))
    router_key = get_selected_router(query.from_user.id)

    try:
        kicked = await run_blocking(hotspot_manager.kick_user, router_key, username) or []
        fresh_user = await run_blocking(hotspot_manager.get_user, router_key, context.user_data.get("edit_user_id"))
        if fresh_user:
            context.user_data["edit_user_data"] = fresh_user
        is_disabled = str((fresh_user or user_data).get("disabled", "no")).lower() in ("yes", "true", "1")
        if kicked:
            msg = f"✅ تم طرد المستخدم من {len(kicked)} جهاز:\n" + "\n".join(f"• {n}" for n in kicked)
        else:
            msg = NO_ACTIVE_DEVICES_FOR_USER
        await query.edit_message_text(msg, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled))
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="hotspot_edit_kick",
            reply_markup=get_edit_field_keyboard(),
        )

    return WAITING_EDIT_VALUE


@admin_only
async def hotspot_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    field = query.data.replace("edit_field_", "")
    context.user_data["edit_field"] = field

    field_names = EDIT_FIELD_NAMES

    if field == "toggle_disabled":
        router_key = get_selected_router(query.from_user.id)
        user_id = context.user_data.get("edit_user_id")
        user_data = context.user_data.get("edit_user_data", {})
        if not router_key or not user_id or not user_data:
            await query.edit_message_text(USER_NOT_SELECTED)
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END

        current_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        new_disabled = not current_disabled
        new_value = "yes" if new_disabled else "no"

        try:
            await run_blocking(hotspot_manager.edit_user, router_key, user_id, disabled=new_value)
            await run_blocking(log_action, "toggle_disabled", user_id, router_key, query.from_user.id)

            user_data["disabled"] = new_value
            is_disabled = new_disabled
            toggle_msg = TOGGLE_DISABLED_OFF if new_disabled else TOGGLE_DISABLED_ON

            text = f"{toggle_msg}\n\n" + EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user_data))
            await query.edit_message_text(text, reply_markup=get_edit_field_keyboard(is_disabled=is_disabled))
        except Exception as e:
            await send_error(
                update, context, e, router_key=router_key,
                log_extra="hotspot_edit_toggle_disabled",
                reply_markup=get_edit_field_keyboard(),
            )
        return WAITING_EDIT_VALUE

    if field == "profile":
        router_key = get_selected_router(query.from_user.id)
        try:
            profile_names = await fetch_and_cache_profiles(
                context, router_key, source=PROFILE_SOURCE_HOTSPOT,
            )
            await edit_clean(
                query,
                context,
                CHOOSE_NEW_PROFILE,
                keyboard=get_profile_keyboard(
                    profile_names, "edit_profile", "edit_back_to_fields"
                ),
            )
            return WAITING_EDIT_VALUE
        except Exception as e:
            await send_error(
                update, context, e, router_key=router_key,
                log_extra="hotspot_edit_field",
                reply_markup=get_edit_field_keyboard(),
            )
            return WAITING_EDIT_VALUE

    user_data = context.user_data.get("edit_user_data", {})
    api_key = FIELD_API_KEYS.get(field, field)
    current_value = user_data.get(api_key, "فارغ")
    if field == "bytes":
        current_value = format_bytes(current_value)

    await edit_clean(
        query,
        context,
        f"✏️ أرسل القيمة الجديدة للحقل «{field_names.get(field, field)}»:\n"
        f"📌 القيمة الحالية: <code>{current_value}</code>",
        keyboard=get_back_keyboard("edit_back_to_fields"),
    )
    return WAITING_EDIT_VALUE


@admin_only
async def edit_profile_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    profile = resolve_profile_from_callback(context, query.data, "edit_profile_")
    if not profile:
        await query.edit_message_text(ERROR_OCCURRED.format(INVALID_PROFILE))
        return WAITING_EDIT_VALUE
    router_key = get_selected_router(query.from_user.id)
    user_id = context.user_data.get("edit_user_id")
    try:
        await run_blocking(
            hotspot_manager.edit_user, router_key, user_id, profile=profile
        )
        await run_blocking(log_action, "edit_user", user_id, router_key, query.from_user.id)
        user_data = context.user_data.get("edit_user_data", {})
        if user_data:
            user_data["profile"] = profile
        is_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        await query.edit_message_text(
            EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user_data or {})),
            reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
        )
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="edit_profile_selected",
            reply_markup=get_edit_field_keyboard(),
        )
    return WAITING_EDIT_VALUE


@admin_only
async def edit_back_to_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    user_data = context.user_data.get("edit_user_data", {})
    if user_data:
        is_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        await query.edit_message_text(
            EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user_data)),
            reply_markup=get_edit_field_keyboard(is_disabled=is_disabled),
        )
    else:
        await query.edit_message_text(EDIT_USER_PROMPT, reply_markup=get_cancel_keyboard())
        return WAITING_EDIT_FIELD
    return WAITING_EDIT_VALUE


@admin_only
async def edit_back_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(EDIT_USER_PROMPT, reply_markup=get_cancel_keyboard())
    return WAITING_EDIT_FIELD


@admin_only
async def hotspot_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text.strip()
    field = context.user_data.get("edit_field")
    user_id = context.user_data.get("edit_user_id")
    router_key = get_selected_router(update.effective_user.id)

    if not router_key or not user_id or not field:
        await reply_final(update, context, DATA_ERROR)
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    api_field = FIELD_API_KEYS.get(field, field)
    if api_field == "name":
        valid, name_msg = validate_username(new_value)
        if not valid:
            await reply_final(update, context, f"❌ {name_msg}")
            return WAITING_EDIT_VALUE
        current_name = str(context.user_data.get("edit_user_data", {}).get("name", ""))
        if new_value != current_name:
            try:
                exists = await run_blocking(hotspot_manager.user_exists, router_key, new_value)
            except Exception as e:
                await send_error(
                    update, context, e, router_key=router_key,
                    log_extra="hotspot_edit_value:user_exists",
                    reply_markup=get_back_keyboard("edit_back_to_fields"),
                )
                return WAITING_EDIT_VALUE
            if exists:
                await reply_final(update, context, DUPLICATE_USER)
                return WAITING_EDIT_VALUE
    if api_field == "limit-bytes-total":
        try:
            new_value = validate_bytes_input(new_value)
        except ValueError as e:
            await reply_final(update, context, str(e))
            return WAITING_EDIT_VALUE

    try:
        user_data = context.user_data.get("edit_user_data", {})
        user_name = user_data.get("name", "") or user_id
        await run_blocking(
            hotspot_manager.edit_user, router_key, user_id, **{api_field: new_value}
        )
        await run_blocking(log_action, "edit_user", user_id, router_key, update.effective_user.id)

        user_data[api_field] = new_value

        kick_msg = ""
        if field == "bytes":
            if user_name:
                kicked = await run_blocking(
                    hotspot_manager.kick_user, router_key, user_name
                )
                if kicked:
                    kick_msg = f"\n🔄 تم طرد المستخدم من {len(kicked)} جهاز"

        is_disabled = str(user_data.get("disabled", "no")).lower() in ("yes", "true", "1")
        text = (
            f"✅ تم التعديل بنجاح{kick_msg}\n\n"
            + EDIT_SELECT_FIELD.format(hotspot_manager.format_user(user_data))
        )
        await send_step(update, context, text, get_edit_field_keyboard(is_disabled=is_disabled))
        return WAITING_EDIT_VALUE
    except Exception as e:
        await send_error(
            update, context, e, router_key=router_key,
            log_extra="hotspot_edit_value",
            reply_markup=get_back_keyboard("edit_back_to_fields"),
        )
        return WAITING_EDIT_VALUE
