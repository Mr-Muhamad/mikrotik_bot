import logging
import sqlite3

from librouteros.exceptions import LibRouterosError
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.handler_utils import ack_callback, parse_router_id
from bot.keyboards import (
    get_delete_router_confirm_keyboard,
    get_main_keyboard,
    get_router_action_keyboard,
    get_router_keyboard,
    get_saved_routers_keyboard,
)
from bot.messages import (
    CANCELLED,
    DELETE_ROUTER_CONFIRM,
    REFRESHING_ROUTERS,
    ROUTER_DELETED,
    ROUTER_NO_CREDENTIALS,
    ROUTER_NOT_FOUND,
    SAVED_ROUTER_OFFLINE,
    SAVED_ROUTER_ONLINE,
    SAVED_ROUTERS,
    SAVED_ROUTERS_EMPTY,
    UNKNOWN_NAME,
)
from bot.router_selector import set_selected_router
from config import ROUTER_KEY_PREFIX
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from core.watchdog import check_router_health
from database.repositories.audit_logs import log_action
from database.repositories.routers import (
    delete_router,
    get_router_by_id,
    get_router_display_name,
    get_saved_routers,
    update_router_identity,
    update_router_last_seen,
)
from utils.admin_decorator import admin_only, require_role, reset_rate_limit
from utils.async_blocking import run_blocking
from utils.chat_cleaner import edit_clean
from utils.error_response import send_error

logger = logging.getLogger(__name__)


def _build_router_status_text(routers: list[RouterOSRow]) -> str:
    lines = []
    for r in routers:
        identity = r.get("identity", "Unknown")
        ip = r.get("ip_address", "")
        name = identity if identity != "Unknown" else ip
        status = (
            SAVED_ROUTER_ONLINE.format(name, ip)
            if r.get("version")
            else SAVED_ROUTER_OFFLINE.format(name, ip)
        )
        lines.append(status)
    return SAVED_ROUTERS.format("\n\n".join(lines))


@admin_only
async def saved_routers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all saved routers with online/offline status.

    Args:
        update: Callback query or command triggering the list.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    user_id = update.effective_user.id if update.effective_user else 0
    from config import ADMIN_IDS

    owner_id = None if user_id in ADMIN_IDS else user_id
    try:
        routers = await run_blocking(get_saved_routers, active_only=True, owner_id=owner_id)
    except sqlite3.Error as e:
        await send_error(
            update,
            context,
            e,
            log_extra="saved_routers_list",
            reply_markup=get_router_keyboard(),
        )
        return
    if not routers:
        msg = SAVED_ROUTERS_EMPTY
        if query:
            await query.edit_message_text(msg, reply_markup=get_router_keyboard())
        else:
            await update.message.reply_text(msg, reply_markup=get_router_keyboard())
        return

    text = _build_router_status_text(routers)
    if query:
        await edit_clean(query, context, text, get_saved_routers_keyboard(routers))
    else:
        await update.message.reply_text(text, reply_markup=get_saved_routers_keyboard(routers))
    reset_rate_limit(update.effective_user.id)


@admin_only
async def saved_router_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details and action buttons for a selected saved router.

    Args:
        update: Callback query with saved_router_{id} in callback_data.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    if query is None:
        return
    router_id = await parse_router_id(query, "saved_router_")
    if router_id is None:
        return
    router = await run_blocking(get_router_by_id, router_id)
    if not router:
        await query.edit_message_text(ROUTER_NOT_FOUND)
        return
    name = get_router_display_name(router)
    version = router.get("version", UNKNOWN_NAME)
    board = router.get("board", UNKNOWN_NAME)
    ip = router["ip_address"]
    port = router["port"]
    has_creds = "✅" if router.get("username") else "❌"
    await edit_clean(
        query,
        context,
        f"🌐 {name}\n📍 {ip}:{port}\n📋 v{version}\n🔧 {board}\n🔑 بيانات الاتصال: {has_creds}",
        get_router_action_keyboard(router_id),
    )
    reset_rate_limit(query.from_user.id)


@admin_only
async def connect_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect to a saved router using stored credentials and set it as selected.

    Args:
        update: Callback query with connect_router_{id} in callback_data.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    if query is None:
        return
    router_id = await parse_router_id(query, "connect_router_")
    if router_id is None:
        return
    router = await run_blocking(get_router_by_id, router_id)
    if not router or not router.get("username"):
        await query.edit_message_text(ROUTER_NO_CREDENTIALS)
        return
    await query.edit_message_text(
        f"⏳ جاري الاتصال بـ {router.get('identity', router['ip_address'])}..."
    )
    try:
        success, version, identity = await run_blocking(
            mikrotik_api.test_connection,
            router["ip_address"],
            router["username"],
            router["password"],
            router["port"],
        )
        if success:
            await run_blocking(update_router_last_seen, router_id)
            if identity and identity != "Unknown":
                await run_blocking(update_router_identity, router_id, identity)
            router_key = f"{ROUTER_KEY_PREFIX}{router_id}"
            set_selected_router(query.from_user.id, router_key)
            await run_blocking(check_router_health, router_key)
            await run_blocking(
                log_action,
                "connect_saved",
                router["ip_address"],
                identity,
                query.from_user.id,
            )
            await edit_clean(
                query,
                context,
                f"✅ تم الاتصال بنجاح!\n\n🌐 {identity}\n📋 v{version}\n📍 {router['ip_address']}",
                get_main_keyboard(),
            )
            reset_rate_limit(query.from_user.id)
        else:
            await query.edit_message_text(
                version,
                reply_markup=get_router_action_keyboard(router_id),
            )
    except Exception as e:  # noqa: BLE001
        await send_error(
            update,
            context,
            e,
            router_key=f"{ROUTER_KEY_PREFIX}{router_id}",
            log_extra="connect_router",
        )


@require_role("admin")
@admin_only
async def delete_router_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation dialog before deleting a saved router.

    Args:
        update: Callback query with delete_router_{id} in callback_data.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    if query is None:
        return
    router_id = await parse_router_id(query, "delete_router_")
    if router_id is None:
        return
    router = await run_blocking(get_router_by_id, router_id, decrypt=False)
    if not router:
        await query.edit_message_text(ROUTER_NOT_FOUND)
        return
    name = router.get("identity", router["ip_address"])
    await edit_clean(
        query,
        context,
        DELETE_ROUTER_CONFIRM.format(name),
        get_delete_router_confirm_keyboard(router_id),
    )


@require_role("admin")
@admin_only
async def delete_router_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete the router from DB or cancel based on user confirmation.

    Args:
        update: Callback query with confirm_delete_router_{yes|no}_{id}.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    if query is None:
        return
    if query.data.startswith("confirm_delete_router_yes_"):
        router_id = await parse_router_id(query, "confirm_delete_router_yes_")
        if router_id is None:
            return
        router = await run_blocking(get_router_by_id, router_id, decrypt=False)
        router_identity = (
            router.get("identity", router.get("ip_address", "")) if router else "unknown"
        )
        await run_blocking(delete_router, router_id)
        await run_blocking(
            log_action,
            "delete_router",
            router_identity,
            f"id:{router_id}",
            query.from_user.id,
        )
        await query.edit_message_text(ROUTER_DELETED, reply_markup=get_router_keyboard())
    elif query.data.startswith("confirm_delete_router_no_"):
        await query.edit_message_text(CANCELLED, reply_markup=get_router_keyboard())


@admin_only
async def refresh_routers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Probe all saved routers and update their online/offline status.

    Args:
        update: Callback query from the refresh button.
        context: Conversation context.

    Returns:
        None (single-step, no state constant).
    """
    query = await ack_callback(update)
    if query is None:
        return
    await query.edit_message_text(REFRESHING_ROUTERS)
    try:
        routers = await run_blocking(get_saved_routers, active_only=True, decrypt=True)
        updated = 0
        for r in routers:
            try:
                success, _, _ = await run_blocking(
                    mikrotik_api.test_connection,
                    r["ip_address"],
                    r.get("username", ""),
                    r.get("password", ""),
                    r["port"],
                )
                if success:
                    await run_blocking(update_router_last_seen, r["id"])
                    updated += 1
            except (LibRouterosError, OSError) as e:
                logger.warning(
                    "refresh_routers: connection failed for %s: %s", r.get("identity", r["ip_address"]), e  # noqa: E501
                )

        routers = await run_blocking(get_saved_routers, active_only=True)
        text = _build_router_status_text(routers)
        await query.edit_message_text(
            f"{text}\n\n✅ تم تحديث {updated} روتر",
            reply_markup=get_saved_routers_keyboard(routers),
        )
        reset_rate_limit(query.from_user.id)
    except sqlite3.Error as e:
        await send_error(
            update,
            context,
            e,
            log_extra="refresh_routers",
        )
