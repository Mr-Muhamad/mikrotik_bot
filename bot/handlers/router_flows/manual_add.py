import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.callback_constants import (
    manual_add_confirm as build_manual_add_confirm,
)
from bot.handlers.constants import (
    WAITING_MANUAL_ALIAS,
    WAITING_MANUAL_CONFIRM,
    WAITING_MANUAL_IP,
    WAITING_MANUAL_PASS,
    WAITING_MANUAL_PORT,
    WAITING_MANUAL_USER,
)
from bot.keyboards import get_main_keyboard, get_router_keyboard
from bot.messages import (
    CANCELLED,
    MANUAL_ADD_ALIAS_PROMPT,
    MANUAL_ADD_CONFIRM,
    MANUAL_ADD_CONN_FAILED,
    MANUAL_ADD_DUPLICATE,
    MANUAL_ADD_INVALID,
    MANUAL_ADD_IP_PROMPT,
    MANUAL_ADD_PASS_PROMPT,
    MANUAL_ADD_PORT_PROMPT,
    MANUAL_ADD_SAVED,
    MANUAL_ADD_USER_PROMPT,
)
from bot.router_selector import cleanup_state, nav_set, set_selected_router
from config import DEFAULT_API_PORT, ROUTER_KEY_PREFIX
from core.exceptions import RouterAlreadyExistsError
from core.mikrotik_api import mikrotik_api
from database.models import (
    log_action,
    update_router_identity,
    update_router_last_seen,
)
from database.repositories.routers import get_router_by_ip, save_manual_router
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import send_step
from utils.error_response import send_error
from utils.validators import (
    validate_ip,
    validate_password,
    validate_port,
    validate_username,
)

logger = logging.getLogger(__name__)


def _confirm_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تأكيد", callback_data=build_manual_add_confirm(True)),
                InlineKeyboardButton("❌ إلغاء", callback_data=build_manual_add_confirm(False)),
            ],
        ]
    )


@require_role("admin")
async def manual_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate the manual router add flow and prompt for the IP address.

    Args:
        update: Callback query or message triggering the flow.
        context: Conversation context.

    Returns:
        WAITING_MANUAL_IP.
    """
    query = update.callback_query
    cancel_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_edit")]]
    )
    if query:
        await safe_answer_callback(query)
        cleanup_state(query.from_user.id, context.user_data)
        nav_set(context, "saved_routers")
        await query.edit_message_text(MANUAL_ADD_IP_PROMPT, reply_markup=cancel_keyboard)
    else:
        cleanup_state(update.effective_user.id, context.user_data)
        nav_set(context, "saved_routers")
        await update.message.reply_text(MANUAL_ADD_IP_PROMPT, reply_markup=cancel_keyboard)
    return WAITING_MANUAL_IP


@admin_only
async def manual_add_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate the IP address, check for duplicates, and prompt for port.

    Args:
        update: Message containing the IP address.
        context: Conversation context storing manual_ip.

    Returns:
        WAITING_MANUAL_PORT or WAITING_MANUAL_IP on invalid input.
    """
    raw = update.message.text.strip()
    ok, msg = validate_ip(raw)
    if not ok:
        await send_step(update, context, MANUAL_ADD_INVALID.format(msg))
        return WAITING_MANUAL_IP
    existing = await run_blocking(get_router_by_ip, raw)
    if existing:
        await send_step(
            update,
            context,
            MANUAL_ADD_DUPLICATE.format(raw, existing.get("identity", raw)),
        )
        return WAITING_MANUAL_IP
    _cancel_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")]]
    )
    context.user_data["manual_ip"] = raw
    await send_step(
        update,
        context,
        MANUAL_ADD_PORT_PROMPT.format(DEFAULT_API_PORT),
        keyboard=_cancel_kb,
    )
    return WAITING_MANUAL_PORT


@admin_only
async def manual_add_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate the port number and prompt for the API username.

    Args:
        update: Message containing the port number (empty for default).
        context: Conversation context storing manual_port.

    Returns:
        WAITING_MANUAL_USER or WAITING_MANUAL_PORT on invalid input.
    """
    _cancel_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")]]
    )
    raw = update.message.text.strip()
    if raw == "":
        port = DEFAULT_API_PORT
    else:
        ok, msg = validate_port(raw)
        if not ok:
            await send_step(update, context, MANUAL_ADD_INVALID.format(msg), keyboard=_cancel_kb)
            return WAITING_MANUAL_PORT
        port = int(raw)
    context.user_data["manual_port"] = port
    await send_step(update, context, MANUAL_ADD_USER_PROMPT, keyboard=_cancel_kb)
    return WAITING_MANUAL_USER


@admin_only
async def manual_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate the username and prompt for the password.

    Args:
        update: Message containing the username text.
        context: Conversation context storing manual_user.

    Returns:
        WAITING_MANUAL_PASS or WAITING_MANUAL_USER on invalid input.
    """
    _cancel_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")]]
    )
    raw = update.message.text.strip()
    ok, msg = validate_username(raw)
    if not ok:
        await send_step(update, context, MANUAL_ADD_INVALID.format(msg), keyboard=_cancel_kb)
        return WAITING_MANUAL_USER
    context.user_data["manual_user"] = raw
    await send_step(update, context, MANUAL_ADD_PASS_PROMPT, keyboard=_cancel_kb)
    return WAITING_MANUAL_PASS


@admin_only
async def manual_add_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate the password and prompt for an optional alias.

    Args:
        update: Message containing the password text.
        context: Conversation context storing manual_pass.

    Returns:
        WAITING_MANUAL_ALIAS or WAITING_MANUAL_PASS on invalid input.
    """
    _cancel_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")]]
    )
    raw = update.message.text.strip()
    ok, msg = validate_password(raw)
    if not ok:
        await send_step(update, context, MANUAL_ADD_INVALID.format(msg), keyboard=_cancel_kb)
        return WAITING_MANUAL_PASS
    context.user_data["manual_pass"] = raw
    await send_step(update, context, MANUAL_ADD_ALIAS_PROMPT, keyboard=_cancel_kb)
    return WAITING_MANUAL_ALIAS


@admin_only
async def manual_add_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the alias and display the confirmation summary.

    Args:
        update: Message containing the alias text or /skip.
        context: Conversation context storing manual_alias.

    Returns:
        WAITING_MANUAL_CONFIRM.
    """
    raw = update.message.text.strip()
    alias = "" if (raw == "/skip" or raw == "") else raw
    context.user_data["manual_alias"] = alias
    ip = context.user_data["manual_ip"]
    port = context.user_data["manual_port"]
    user = context.user_data["manual_user"]
    await send_step(
        update,
        context,
        MANUAL_ADD_CONFIRM.format(ip, port, user, alias or "-"),
        keyboard=_confirm_keyboard(),
    )
    return WAITING_MANUAL_CONFIRM


@require_role("admin")
async def manual_add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the router to DB, test the connection, and set it as selected.

    Args:
        update: Callback query with manual_add_confirm_{bool} in callback_data.
        context: Conversation context with manual_ip/port/user/pass/alias.

    Returns:
        ConversationHandler.END.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    if query.data == build_manual_add_confirm(False):
        await query.edit_message_text(CANCELLED, reply_markup=get_router_keyboard())
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    ip = context.user_data.get("manual_ip")
    port = context.user_data.get("manual_port")
    user = context.user_data.get("manual_user")
    pw = context.user_data.get("manual_pass")
    alias = context.user_data.get("manual_alias", "")
    user_id = query.from_user.id

    try:
        router_id = await run_blocking(save_manual_router, ip, port, user, pw, alias, user_id)
    except RouterAlreadyExistsError:
        await query.edit_message_text(
            MANUAL_ADD_DUPLICATE.format(ip, ip), reply_markup=get_router_keyboard()
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    except Exception as e:  # noqa: BLE001
        await send_error(update, context, e, log_extra="manual_add_save")
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    try:
        success, version, identity = await run_blocking(
            mikrotik_api.test_connection, ip, user, pw, port
        )
        if success:
            await run_blocking(update_router_last_seen, router_id)
            if identity and identity != "Unknown":
                await run_blocking(update_router_identity, router_id, identity)
            display = identity or ip
            router_key = f"{ROUTER_KEY_PREFIX}{router_id}"
            set_selected_router(query.from_user.id, router_key)
            from core.router_info import detect_router_system
            from core.watchdog import check_router_health

            await run_blocking(check_router_health, router_key)
            await run_blocking(detect_router_system, router_key)
            await run_blocking(log_action, "add_router_manual", ip, display, query.from_user.id)
            await query.edit_message_text(
                MANUAL_ADD_SAVED.format(display, ip), reply_markup=get_main_keyboard()
            )
        else:
            await run_blocking(log_action, "add_router_manual", ip, "offline", query.from_user.id)
            await query.edit_message_text(
                MANUAL_ADD_CONN_FAILED.format(version),
                reply_markup=get_router_keyboard(),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"manual_add confirm test connection failed for {ip}: {e}")
        await run_blocking(log_action, "add_router_manual", ip, "offline", query.from_user.id)
        await query.edit_message_text(
            MANUAL_ADD_CONN_FAILED.format("تعذّر الاتصال للتحقق"),
            reply_markup=get_router_keyboard(),
        )

    cleanup_state(query.from_user.id, context.user_data)
    return ConversationHandler.END
