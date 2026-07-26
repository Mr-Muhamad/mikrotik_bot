import logging
from datetime import UTC, datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import (
    TIME_OPTIONS,
    get_logs_filter_keyboard,
    get_logs_submenu_keyboard,
)
from bot.messages import (
    AUDIT_LIST_EMPTY,
    AUDIT_LIST_HEADER,
    AUDIT_NO_FILTERS,
    AUDIT_PAGE_EMPTY,
    AUDIT_SUBMENU_ACTION,
    AUDIT_SUBMENU_ADMIN,
    AUDIT_SUBMENU_CHOOSE,
    AUDIT_SUBMENU_COUNT,
    AUDIT_SUBMENU_ROUTER,
    AUDIT_SUBMENU_TIME,
    NO_RESULTS,
)
from bot.router_selector import nav_set
from core.mikrotik_client import RouterOSRow
from database.models import (
    UTC_TIMESTAMP_FORMAT,
    get_distinct_log_actions,
    get_distinct_log_admins,
    get_distinct_log_routers,
    get_logs,
    get_logs_count,
)
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_step
from utils.error_response import send_error

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
SUBMENU_PAGE_SIZE = 20

SUBMENU_TITLES = {
    "router": AUDIT_SUBMENU_ROUTER,
    "admin": AUDIT_SUBMENU_ADMIN,
    "action": AUDIT_SUBMENU_ACTION,
    "time": AUDIT_SUBMENU_TIME,
}

_FILTER_KEYS = ("router", "admin_id", "admin_label", "action", "since_days")


def _empty_filters() -> RouterOSRow:
    return {
        "router": None,
        "admin_id": None,
        "admin_label": None,
        "action": None,
        "since_days": None,
    }


def _get_filters(context: ContextTypes.DEFAULT_TYPE) -> RouterOSRow:
    return context.user_data.setdefault("logs_filters", _empty_filters())


def _build_db_filters(filters: dict[str, str | int | None]) -> dict[str, str | int | None]:
    db_filters = {
        "router": filters.get("router"),
        "admin_id": filters.get("admin_id"),
        "action": filters.get("action"),
    }
    since_days = filters.get("since_days")
    if since_days:
        cutoff = datetime.now(UTC) - timedelta(days=float(since_days))
        db_filters["since"] = cutoff.strftime(UTC_TIMESTAMP_FORMAT)
    return db_filters


def _format_filters_short(filters: RouterOSRow) -> str:
    parts = []
    router_val = filters.get("router")
    if router_val:
        parts.append(f"🔍 {str(router_val)}")
    admin_id_val = filters.get("admin_id")
    if admin_id_val is not None:
        admin_label_val = filters.get("admin_label")
        parts.append(f"👤 {str(admin_label_val) if admin_label_val else str(admin_id_val)}")
    action_val = filters.get("action")
    if action_val:
        parts.append(f"⚙️ {str(action_val)}")
    since_days_val = filters.get("since_days")
    if since_days_val:
        label = next((name for name, days in TIME_OPTIONS if days == since_days_val), "")
        parts.append(f"🕓 {label}")
    return " | ".join(parts) if parts else AUDIT_NO_FILTERS


@admin_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show audit log page 0 with the filter menu."""
    logger.info("logs_command: user=%s", update.effective_user.id)
    context.user_data["logs_filters"] = _empty_filters()
    context.user_data["logs_menu"] = None
    context.user_data["logs_sub_page"] = 0
    await _show_logs_page(update, context, page=0, from_callback=False)


@admin_only
async def logs_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open a submenu to pick one filter value."""
    query = update.callback_query
    await safe_answer_callback(query)
    category = query.data.replace("logs_filter_", "")
    try:
        if category == "router":
            options = await run_blocking(get_distinct_log_routers)
            context.user_data["logs_router_options"] = options
            context.user_data["logs_menu"] = "router"
        elif category == "admin":
            options = await run_blocking(get_distinct_log_admins)
            context.user_data["logs_admin_options"] = options
            context.user_data["logs_menu"] = "admin"
        elif category == "action":
            options = await run_blocking(get_distinct_log_actions)
            context.user_data["logs_action_options"] = options
            context.user_data["logs_menu"] = "action"
        elif category == "time":
            context.user_data["logs_menu"] = "time"
        else:
            return
    except Exception as e:
        logger.error("logs_filter_callback failed: %s", e)
        await send_error(update, context, e, log_extra="logs_filter")
        return
    context.user_data["logs_sub_page"] = 0
    await _show_submenu(update, context)


@admin_only
async def logs_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply a chosen filter value and return to the list."""
    query = update.callback_query
    await safe_answer_callback(query)
    data = query.data
    filters = _get_filters(context)
    if data.startswith("logs_set_router_"):
        options = context.user_data.get("logs_router_options", [])
        idx = int(data.replace("logs_set_router_", ""))
        filters["router"] = options[idx] if 0 <= idx < len(options) else None
    elif data.startswith("logs_set_admin_"):
        options = context.user_data.get("logs_admin_options", [])
        idx = int(data.replace("logs_set_admin_", ""))
        if 0 <= idx < len(options):
            admin = options[idx]
            filters["admin_id"] = admin["admin_id"]
            filters["admin_label"] = admin["username"] or str(admin["admin_id"])
        else:
            filters["admin_id"] = None
            filters["admin_label"] = None
    elif data.startswith("logs_set_action_"):
        options = context.user_data.get("logs_action_options", [])
        idx = int(data.replace("logs_set_action_", ""))
        filters["action"] = options[idx] if 0 <= idx < len(options) else None
    elif data.startswith("logs_set_time_"):
        idx = int(data.replace("logs_set_time_", ""))
        filters["since_days"] = TIME_OPTIONS[idx][1] if 0 <= idx < len(TIME_OPTIONS) else None
    context.user_data["logs_menu"] = None
    context.user_data["logs_sub_page"] = 0
    await _show_logs_page(update, context, page=0, from_callback=True)


@admin_only
async def logs_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all active filters and show the full list."""
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["logs_filters"] = _empty_filters()
    context.user_data["logs_menu"] = None
    context.user_data["logs_sub_page"] = 0
    await _show_logs_page(update, context, page=0, from_callback=True)


@admin_only
async def logs_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return from a filter submenu to the list view."""
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["logs_menu"] = None
    await _show_logs_page(update, context, page=0, from_callback=True)


@admin_only
async def logs_subnav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paginate inside a filter submenu."""
    query = update.callback_query
    await safe_answer_callback(query)
    current = context.user_data.get("logs_sub_page", 0)
    data = query.data
    context.user_data["logs_sub_page"] = current + (
        1 if data is not None and "next" in data else -1
    )
    await _show_submenu(update, context)


@admin_only
async def logs_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle page navigation for audit logs (respects active filters)."""
    query = update.callback_query
    await safe_answer_callback(query)
    page_str = query.data.replace("logs_page_", "")
    try:
        page = int(page_str)
    except ValueError:
        page = 0
    await _show_logs_page(update, context, page=page, from_callback=True)


async def _show_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    menu = context.user_data.get("logs_menu")
    page = context.user_data.get("logs_sub_page", 0)
    title = SUBMENU_TITLES.get(menu or "", AUDIT_SUBMENU_CHOOSE)
    if menu == "time":
        options = [name for name, _ in TIME_OPTIONS]
        suffix = "time"
    elif menu == "router":
        options = context.user_data.get("logs_router_options", [])
        suffix = "router"
    elif menu == "admin":
        admins = context.user_data.get("logs_admin_options", [])
        options = [f"{a['username'] or a['admin_id']} (ID {a['admin_id']})" for a in admins]
        suffix = "admin"
    elif menu == "action":
        options = context.user_data.get("logs_action_options", [])
        suffix = "action"
    else:
        options, suffix = [], "router"
    text = AUDIT_SUBMENU_COUNT.format(title=title, count=len(options))
    keyboard = get_logs_submenu_keyboard(suffix, options, page, SUBMENU_PAGE_SIZE)
    if update.callback_query:
        await safe_edit_or_send(update.callback_query, context, text, keyboard)
    else:
        await send_step(update, context, text, keyboard)


async def _show_logs_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0,
    from_callback: bool = False,
) -> None:
    """Display a page of audit logs filtered by the active filter state."""
    filters = _get_filters(context)
    # Cast RouterOSRow to expected filter type for db and keyboard functions
    filter_dict: dict[str, object] = {}
    for k, v in filters.items():
        if v is None:
            filter_dict[k] = None
        elif isinstance(v, (str, int)):
            filter_dict[k] = v
        else:
            filter_dict[k] = str(v)
    db_filters = _build_db_filters(filter_dict)  # type: ignore[arg-type]
    try:
        total = await run_blocking(get_logs_count, db_filters)
    except Exception as e:
        logger.error("get_logs_count failed: %s", e)
        await send_error(update, context, e, log_extra="logs_count")
        return
    header = f"🔎 {_format_filters_short(filters)}"

    if total == 0:
        text = AUDIT_LIST_EMPTY.format(header=header, no_results=NO_RESULTS)
        keyboard = get_logs_filter_keyboard(filter_dict, page, 0)
        nav_set(context, "main_menu")
        if from_callback and update.callback_query:
            await safe_edit_or_send(update.callback_query, context, text, keyboard)
        else:
            await send_step(update, context, text, keyboard)
        return

    offset = page * PAGE_SIZE
    try:
        logs = await run_blocking(get_logs, PAGE_SIZE, offset, db_filters)
    except Exception as e:
        logger.error("get_logs failed: %s", e)
        await send_error(update, context, e, log_extra="logs_fetch")
        return
    if not logs:
        text = AUDIT_PAGE_EMPTY.format(header=header)
        keyboard = get_logs_filter_keyboard(filter_dict, page, total)
        nav_set(context, "main_menu")
        if from_callback and update.callback_query:
            await safe_edit_or_send(update.callback_query, context, text, keyboard)
        else:
            await send_step(update, context, text, keyboard)
        return

    start = offset + 1
    end = min(offset + PAGE_SIZE, total)

    lines = [AUDIT_LIST_HEADER.format(start=start, end=end, total=total), header, ""]
    for log in logs:
        action = str(log.get("action", ""))
        username = str(log.get("username", ""))
        router = str(log.get("router_name", ""))
        ts = str(log.get("timestamp", ""))
        if ts and len(ts) > 16:
            ts = ts[:16]
        lines.append(f"• [{ts}] {action} — {username} @ {router}")

    text = "\n".join(lines)
    keyboard = get_logs_filter_keyboard(filter_dict, page, total)

    nav_set(context, "main_menu")

    if from_callback and update.callback_query:
        await safe_edit_or_send(update.callback_query, context, text, keyboard)
    else:
        await send_step(update, context, text, keyboard)
