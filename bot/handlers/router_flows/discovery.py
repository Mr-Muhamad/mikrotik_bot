import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.constants import WAITING_DISC_PASSWORD, WAITING_DISC_USERNAME
from bot.handlers.handler_utils import ack_callback
from bot.keyboards import (
    get_discovered_routers_keyboard,
    get_main_keyboard,
    get_nav_back_keyboard,
    get_router_keyboard,
)
from bot.messages import (
    DISCOVERY_CONNECTING,
    DISCOVERY_CREDENTIALS,
    DISCOVERY_FAILED,
    DISCOVERY_NO_RESULTS,
    DISCOVERY_PASSWORD,
    DISCOVERY_PERMISSION_ERROR,
    DISCOVERY_RESULTS,
    DISCOVERY_START,
    DISCOVERY_SUCCESS,
    ROUTER_ALREADY_EXISTS,
    ROUTER_UPDATED,
)
from bot.router_selector import cleanup_state, nav_set, set_selected_router
from config import ROUTER_KEY_PREFIX
from core.mikrotik_api import mikrotik_api
from core.network_scanner import discover_routers
from database.models import (
    get_router_by_ip,
    get_router_display_name,
    log_action,
    save_discovered_router,
    update_router_credentials,
)
from utils.admin_decorator import admin_only, reset_rate_limit
from utils.async_blocking import run_blocking
from utils.chat_cleaner import edit_clean, schedule_delete, send_step
from utils.error_response import send_error

logger = logging.getLogger(__name__)


@admin_only
async def discover_routers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = await ack_callback(update)
    await query.edit_message_text(DISCOVERY_START)
    try:
        routers = await discover_routers(mndp_timeout=10)
        if not routers:
            await query.edit_message_text(DISCOVERY_NO_RESULTS, reply_markup=get_router_keyboard())
            return
        results_text = "\n\n".join([r.display_line() for r in routers])
        await edit_clean(
            query,
            context,
            DISCOVERY_RESULTS.format(len(routers), results_text),
            get_discovered_routers_keyboard(routers),
        )
    except PermissionError:
        await query.edit_message_text(
            DISCOVERY_PERMISSION_ERROR, reply_markup=get_router_keyboard()
        )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            log_extra="discover_routers_callback",
            reply_markup=get_router_keyboard(),
        )


@admin_only
async def discovered_router_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = await ack_callback(update)
    cleanup_state(query.from_user.id, context.user_data)
    ip = query.data.replace("disc_router_", "")
    context.user_data["disc_ip"] = ip
    router_db = await run_blocking(get_router_by_ip, ip)
    nav_set(context, "main_menu")

    warning = ""
    if router_db:
        router_name = get_router_display_name(router_db)
        warning = ROUTER_ALREADY_EXISTS.format(ip=ip, name=router_name)

    if router_db and router_db.get("username"):
        context.user_data["disc_router_id"] = router_db["id"]
        context.user_data["disc_username"] = router_db["username"]
        await query.edit_message_text(
            f"{warning}{DISCOVERY_PASSWORD.format(ip)}",
            reply_markup=get_nav_back_keyboard(),
        )
        return WAITING_DISC_PASSWORD

    await query.edit_message_text(
        f"{warning}{DISCOVERY_CREDENTIALS.format(ip)}",
        reply_markup=get_nav_back_keyboard(),
    )
    return WAITING_DISC_USERNAME


@admin_only
async def disc_enter_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["disc_username"] = update.message.text
    ip = context.user_data.get("disc_ip", "")
    await send_step(update, context, DISCOVERY_PASSWORD.format(ip), get_nav_back_keyboard())
    return WAITING_DISC_PASSWORD


@admin_only
async def disc_enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete password message: {e}")

    ip = context.user_data.get("disc_ip", "")
    username = context.user_data.get("disc_username", "")
    status_msg = await update.message.reply_text(DISCOVERY_CONNECTING.format(ip))
    try:
        success, version, identity = await run_blocking(
            mikrotik_api.test_connection, ip, username, password
        )
        if success:
            router_db = await run_blocking(get_router_by_ip, ip)
            is_update = router_db is not None
            if is_update:
                router_id = router_db["id"]
                await run_blocking(update_router_credentials, router_id, username, password)
            else:
                router_id = await run_blocking(
                    save_discovered_router,
                    ip=ip,
                    username=username,
                    password=password,
                    identity=identity,
                    version=version,
                    last_seen=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    owner_id=update.effective_user.id,
                )
            router_key = f"{ROUTER_KEY_PREFIX}{router_id}"
            set_selected_router(update.effective_user.id, router_key)
            from core.router_info import detect_router_system
            from core.watchdog import check_router_health

            await run_blocking(check_router_health, router_key)
            await run_blocking(detect_router_system, router_key)
            await run_blocking(
                log_action, "connect_discovered", ip, identity, update.effective_user.id
            )
            success_msg = (
                ROUTER_UPDATED.format(identity, version, ip)
                if is_update
                else DISCOVERY_SUCCESS.format(identity, version, ip)
            )
            await status_msg.edit_text(
                success_msg,
                reply_markup=get_main_keyboard(),
            )
            reset_rate_limit(update.effective_user.id)
        else:
            await status_msg.edit_text(
                f"{DISCOVERY_FAILED}\n\n{version}", reply_markup=get_router_keyboard()
            )
            await schedule_delete(context, update.effective_chat.id, status_msg.message_id)
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            log_extra="disc_enter_password",
            reply_markup=get_router_keyboard(),
        )
        await schedule_delete(context, update.effective_chat.id, status_msg.message_id)
    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END
