import asyncio
import logging
import time
from collections.abc import Mapping
from datetime import datetime

from librouteros.exceptions import LibRouterosError
from telegram import CallbackQuery, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.messages import (
    WATCHDOG_ACTIVE_HOTSPOT,
    WATCHDOG_ALREADY_RUNNING,
    WATCHDOG_BACK_BTN,
    WATCHDOG_LAST_BACKUP,
    WATCHDOG_LAST_FAIL,
    WATCHDOG_LAST_OK,
    WATCHDOG_NO_ROUTERS,
    WATCHDOG_NOT_CHECKED,
    WATCHDOG_OFFLINE_ALERT,
    WATCHDOG_ONLINE,
    WATCHDOG_ONLINE_ALERT,
    WATCHDOG_QUEUE_UNAVAILABLE,
    WATCHDOG_REFRESH_BTN,
    WATCHDOG_REFRESHING,
    WATCHDOG_STARTED,
    WATCHDOG_STATUS_HEADER,
    WATCHDOG_STOPPED,
    WATCHDOG_VERSION,
)
from config import ADMIN_IDS, ROUTER_KEY_PREFIX, WATCHDOG_FIRST_DELAY, WATCHDOG_INTERVAL
from core.mikrotik_client import RouterOSRow
from core.watchdog import (
    ALERT_RECOVERED,
    ALERT_WENT_OFFLINE,
    check_router_health,
    get_router_status_detail,
    record_check_result,
)
from database.repositories.backups import get_last_backup
from database.repositories.routers import get_saved_routers
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_step
from utils.logging_setup import COMPONENT_SERVICE, bind_component
from utils.request_id import bind_request_id, bind_trace_id, new_request_id, new_trace_id

logger = logging.getLogger(__name__)

JOB_NAME = "router_watchdog"


@admin_only
async def watchdog_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start periodic router health checks."""
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    job_queue = context.job_queue
    if not job_queue:
        await _reply(update, context, query, WATCHDOG_QUEUE_UNAVAILABLE)
        return

    existing = job_queue.get_jobs_by_name(JOB_NAME)
    if existing:
        await _reply(update, context, query, WATCHDOG_ALREADY_RUNNING)
        return

    job_queue.run_repeating(
        _check_all_routers,
        interval=WATCHDOG_INTERVAL,
        first=WATCHDOG_FIRST_DELAY,
        name=JOB_NAME,
        job_kwargs={"max_instances": 1},
    )
    await _reply(update, context, query, WATCHDOG_STARTED)


@admin_only
async def watchdog_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop periodic router health checks."""
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    job_queue = context.job_queue
    if not job_queue:
        return

    existing = job_queue.get_jobs_by_name(JOB_NAME)
    for job in existing:
        job.schedule_removal()

    await _reply(update, context, query, WATCHDOG_STOPPED)


@admin_only
async def watchdog_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current health status of all saved routers."""
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    routers = get_saved_routers(active_only=True)
    if not routers:
        await _reply(update, context, query, WATCHDOG_NO_ROUTERS)
        return

    lines = [WATCHDOG_STATUS_HEADER]
    for r in routers:
        lines.extend(await _format_router_status(r))

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    from bot.handlers.callback_constants import CALLBACKS

    keyboard = [
        [InlineKeyboardButton(WATCHDOG_REFRESH_BTN, callback_data=CALLBACKS["watchdog_refresh"])],
        [InlineKeyboardButton(WATCHDOG_BACK_BTN, callback_data=CALLBACKS["main_menu"])],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await safe_edit_or_send(query, context, "\n".join(lines), keyboard=reply_markup)
    else:
        await update.message.reply_text("\n".join(lines), reply_markup=reply_markup)


async def _format_router_status(r: Mapping[str, object]) -> list[str]:
    """Format a single router's health status into display lines."""
    router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
    identity = r.get("identity", router_key)
    ip = r.get("ip_address", "—")
    alias = r.get("name_alias", "")
    display = alias if alias else identity
    detail = await run_blocking(get_router_status_detail, router_key)
    raw_last_ok = detail.get("last_ok")
    raw_last_fail = detail.get("last_fail")
    version = detail.get("version") or "—"
    active_users = detail.get("active_users")
    active_text = str(active_users) if active_users is not None else "—"

    last_ok_dt = _parse_iso(raw_last_ok)
    last_fail_dt = _parse_iso(raw_last_fail)

    if detail.get("online"):
        indicator = "🟢"
        detail_line = (
            WATCHDOG_LAST_OK.format(date=last_ok_dt.strftime("%Y-%m-%d %H:%M"))
            if last_ok_dt
            else WATCHDOG_ONLINE
        )
    elif last_fail_dt:
        indicator = "🔴"
        detail_line = WATCHDOG_LAST_FAIL.format(date=last_fail_dt.strftime("%Y-%m-%d %H:%M"))
    else:
        indicator = "⚪"
        detail_line = WATCHDOG_NOT_CHECKED

    result = [
        f"{indicator} <b>{display}</b> ({ip})",
        WATCHDOG_VERSION.format(version=version),
        f"   ├─ {detail_line}",
        WATCHDOG_ACTIVE_HOTSPOT.format(count=active_text),
    ]

    last_backup = await run_blocking(get_last_backup, router_key)
    if last_backup:
        backup_icon = "✅" if last_backup.get("status") == "success" else "❌"
        backup_text = (
            f"{backup_icon} {last_backup.get('backup_type')} ({last_backup.get('created_at')})"
        )
    else:
        backup_text = "—"
    result.append(WATCHDOG_LAST_BACKUP.format(backup=backup_text))
    return result


def _parse_iso(raw: object) -> datetime | None:
    """Parse an ISO datetime string, returning None on failure."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


@admin_only
async def watchdog_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force an immediate ping to all routers and refresh status."""
    query = update.callback_query
    await safe_answer_callback(query, WATCHDOG_REFRESHING)
    await _check_all_routers(context)
    await watchdog_status(update, context)


async def _reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery | None,
    text: str,
) -> None:
    """Send or edit in place depending on whether triggered from a callback."""
    if query:
        await safe_edit_or_send(query, context, text)
    else:
        await send_step(update, context, text)


async def _check_all_routers(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: check all saved routers concurrently and send alerts."""
    trace_id = new_trace_id()
    request_id = new_request_id()
    with bind_trace_id(trace_id):
        with bind_request_id(request_id):
            with bind_component(COMPONENT_SERVICE):
                routers = await run_blocking(get_saved_routers, active_only=True)
                if not routers:
                    return

                start = time.monotonic()
                results = await asyncio.gather(
                    *[_check_single(r, context) for r in routers],
                    return_exceptions=True,
                )
                duration_ms = (time.monotonic() - start) * 1000
                online_count = sum(1 for r in results if isinstance(r, bool) and r)
                offline_count = sum(1 for r in results if isinstance(r, bool) and not r)
                error_count = sum(1 for r in results if not isinstance(r, bool))
                logger.info(
                    "Watchdog check complete: %d routers, %d online, %d offline, %d errors, %.1fms",
                    len(routers),
                    online_count,
                    offline_count,
                    error_count,
                    duration_ms,
                    extra={
                        "component": COMPONENT_SERVICE,
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "success": error_count == 0,
                        "duration_ms": duration_ms,
                    },
                )


async def _check_single(r: RouterOSRow, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check a single router's health and send alerts on status change."""
    if not r.get("username"):
        return False

    router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
    identity = r.get("identity", router_key)

    try:
        result = await run_blocking(check_router_health, router_key)
        is_online = bool(result["online"])
    except (LibRouterosError, OSError) as e:
        logger.error(
            f"Watchdog check failed for {router_key}: {e}",
            extra={"component": COMPONENT_SERVICE},
        )
        return False

    action = record_check_result(router_key, is_online)
    if action == ALERT_WENT_OFFLINE:
        await _notify_admins(context, WATCHDOG_OFFLINE_ALERT.format(identity=identity))
        logger.warning(f"Router {identity} went offline", extra={"component": COMPONENT_SERVICE})
    elif action == ALERT_RECOVERED:
        await _notify_admins(context, WATCHDOG_ONLINE_ALERT.format(identity=identity))
        logger.info(f"Router {identity} recovered", extra={"component": COMPONENT_SERVICE})
    return is_online


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a notification to all configured admins."""
    from telegram.error import RetryAfter

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, parse_mode="HTML")
        except RetryAfter as e:
            from datetime import timedelta

            delay = (
                float(e.retry_after.total_seconds())
                if isinstance(e.retry_after, timedelta)
                else float(e.retry_after)
            )
            logger.warning(f"Rate limited by Telegram, waiting {delay}s for admin {admin_id}")
            await asyncio.sleep(delay)
            try:
                await context.bot.send_message(admin_id, text, parse_mode="HTML")
            except TelegramError as retry_err:
                logger.error(f"Failed to notify admin {admin_id} after RetryAfter: {retry_err}")
        except TelegramError as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")


# Public alias — external callers (e.g. main.py) should use this name.
check_all_routers = _check_all_routers
