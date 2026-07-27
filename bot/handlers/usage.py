import logging

from librouteros.exceptions import LibRouterosError
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.constants import WAITING_USAGE_QUERY
from bot.keyboards import get_back_keyboard
from bot.messages import (
    NO_ROUTER_SELECTED,
    USAGE_BYTES_IN,
    USAGE_BYTES_OUT,
    USAGE_BYTES_TOTAL,
    USAGE_COMMENT_LABEL,
    USAGE_CURRENT_ACTIVE,
    USAGE_DEVICE_LINE,
    USAGE_HEADER,
    USAGE_LIMIT_LABEL,
    USAGE_NO_ACTIVE,
    USAGE_NO_LIMIT,
    USAGE_NO_ROUTER,
    USAGE_PASSWORD_LABEL,
    USAGE_PROFILE_LABEL,
    USAGE_PROMPT,
    USAGE_SERVER,
    USAGE_STATUS,
    USAGE_STATUS_ACTIVE,
    USAGE_STATUS_DISABLED,
    USAGE_UPTIME_LABEL,
    USER_NOT_FOUND,
)
from bot.router_selector import cleanup_state, get_selected_router, nav_set
from core.hotspot_manager import hotspot_manager
from core.mikrotik_client import RouterOSRow
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.chat_cleaner import send_step
from utils.error_response import send_error
from utils.formatters import format_bytes

logger = logging.getLogger(__name__)

MASKED_PASSWORD = "********"


@admin_only
async def usage_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to enter a Hotspot username for usage report.

    Args:
        update: Callback or message triggering the flow.
        context: Conversation context with router_key in user_data.

    Returns:
        WAITING_USAGE_QUERY state constant.
    """
    query = update.callback_query
    if query:
        await query.answer()
    cleanup_state(update.effective_user.id, context.user_data)
    nav_set(context, "menu_hotspot")
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        router_key = context.user_data.get("router_key")
    if not router_key:
        await send_step(update, context, NO_ROUTER_SELECTED)
        return ConversationHandler.END
    context.user_data["usage_router"] = router_key
    await send_step(update, context, USAGE_PROMPT)
    return WAITING_USAGE_QUERY


@admin_only
async def usage_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a Hotspot user and display usage report.

    Args:
        update: Message with search term (username, MAC, or IP).
        context: Conversation context with usage_router in user_data.

    Returns:
        WAITING_USAGE_QUERY if not found, ConversationHandler.END on success.
    """
    search_term = update.message.text.strip()
    router_key = context.user_data.get("usage_router")

    if not router_key:
        await send_step(update, context, USAGE_NO_ROUTER)
        return ConversationHandler.END

    try:
        users = await run_blocking(hotspot_manager.search_users, router_key, search_term)
    except (LibRouterosError, OSError) as e:
        logger.error(f"Usage search failed: {e}")
        await send_error(update, context, e, router_key=router_key, log_extra="usage_search")
        return ConversationHandler.END

    if not users:
        await send_step(update, context, USER_NOT_FOUND)
        return WAITING_USAGE_QUERY

    await _show_usage_report(update, context, users[0], router_key)
    return ConversationHandler.END


async def _show_usage_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user: RouterOSRow, router_key: str
):
    name = user.get("name", "—")
    disabled = str(user.get("disabled", "false")).lower() == "true"
    status = USAGE_STATUS_DISABLED if disabled else USAGE_STATUS_ACTIVE
    profile = user.get("profile", "—")
    password = user.get("password", "")
    comment = user.get("comment", "")
    server = user.get("server", "—")

    bytes_in = user.get("bytes-in", "0")
    bytes_out = user.get("bytes-out", "0")
    try:
        total_bytes = int(str(bytes_in)) + int(str(bytes_out))
        total_str = format_bytes(str(total_bytes))
        in_str = format_bytes(str(bytes_in))
        out_str = format_bytes(str(bytes_out))
    except (ValueError, TypeError):
        in_str = out_str = total_str = "—"

    limit_raw = user.get("limit-bytes-total", "")
    limit_str = format_bytes(limit_raw) if limit_raw else USAGE_NO_LIMIT

    uptime_raw = user.get("limit-uptime", "")
    uptime_str = uptime_raw if uptime_raw else USAGE_NO_LIMIT

    lines = [
        USAGE_HEADER.format(username=name),
        USAGE_STATUS.format(status=status),
        USAGE_SERVER.format(server=server),
        "",
        USAGE_PROFILE_LABEL.format(profile=profile),
    ]
    if password:
        lines.append(USAGE_PASSWORD_LABEL.format(password=MASKED_PASSWORD))
    lines.append(USAGE_LIMIT_LABEL.format(limit=limit_str))
    if uptime_str != USAGE_NO_LIMIT:
        lines.append(USAGE_UPTIME_LABEL.format(uptime=uptime_str))
    lines.append(USAGE_COMMENT_LABEL.format(comment=comment))
    lines.append("")
    lines.append(USAGE_BYTES_IN.format(bytes=in_str))
    lines.append(USAGE_BYTES_OUT.format(bytes=out_str))
    lines.append(USAGE_BYTES_TOTAL.format(bytes=total_str))
    lines.append("")

    try:
        active_list = await run_blocking(hotspot_manager.search_hosts, router_key, name)
        if active_list:
            active_lines = []
            for h in active_list:
                addr = h.get("address", "—")
                mac = h.get("mac-address", "—")
                uptime = h.get("uptime", "—")
                active_lines.append(USAGE_DEVICE_LINE.format(address=addr, mac=mac, uptime=uptime))
            lines.append(USAGE_CURRENT_ACTIVE.format(devices="\n".join(active_lines)))
        else:
            lines.append(USAGE_NO_ACTIVE)
    except (LibRouterosError, OSError):
        lines.append(USAGE_NO_ACTIVE)

    await send_step(update, context, "\n".join(lines), get_back_keyboard("menu_hotspot"))


__all__ = ["usage_start", "usage_query"]
