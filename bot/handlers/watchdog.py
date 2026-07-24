import asyncio
import logging

from telegram import Update
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
from config import ADMIN_IDS, ROUTER_KEY_PREFIX, WATCHDOG_INTERVAL
from core.watchdog import (
    ALERT_RECOVERED,
    ALERT_WENT_OFFLINE,
    check_router_health,
    get_router_status_detail,
    record_check_result,
)
from database.models import get_last_backup, get_saved_routers
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_step

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
        first=10,
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
        router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
        identity = r.get("identity", router_key)
        ip = r.get("ip_address", "—")
        alias = r.get("name_alias", "")
        display = alias if alias else identity
        detail = await run_blocking(get_router_status_detail, router_key)
        last_ok = detail.get("last_ok")
        last_fail = detail.get("last_fail")
        version = detail.get("version") or "—"
        active_users = detail.get("active_users")
        active_text = str(active_users) if active_users is not None else "—"

        if detail.get("online"):
            indicator = "🟢"
            detail_line = (
                WATCHDOG_LAST_OK.format(date=last_ok.strftime("%Y-%m-%d %H:%M"))
                if last_ok
                else WATCHDOG_ONLINE
            )
        elif last_fail:
            indicator = "🔴"
            detail_line = WATCHDOG_LAST_FAIL.format(date=last_fail.strftime("%Y-%m-%d %H:%M"))
        else:
            indicator = "⚪"
            detail_line = WATCHDOG_NOT_CHECKED

        lines.append(f"{indicator} <b>{display}</b> ({ip})")
        lines.append(WATCHDOG_VERSION.format(version=version))
        lines.append(f"   ├─ {detail_line}")
        lines.append(WATCHDOG_ACTIVE_HOTSPOT.format(count=active_text))
        last_backup = await run_blocking(get_last_backup, router_key)
        if last_backup:
            backup_icon = "✅" if last_backup.get("status") == "success" else "❌"
            backup_text = (
                f"{backup_icon} {last_backup.get('backup_type')} ({last_backup.get('created_at')})"
            )
        else:
            backup_text = "—"
        lines.append(WATCHDOG_LAST_BACKUP.format(backup=backup_text))

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


@admin_only
async def watchdog_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force an immediate ping to all routers and refresh status."""
    query = update.callback_query
    await safe_answer_callback(query, WATCHDOG_REFRESHING)
    await _check_all_routers(context)
    await watchdog_status(update, context)


async def _reply(update, context, query, text: str):
    """Send or edit in place depending on whether triggered from a callback."""
    if query:
        await safe_edit_or_send(query, context, text)
    else:
        await send_step(update, context, text)


async def _check_all_routers(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: check all saved routers concurrently and send alerts."""
    import asyncio

    routers = await run_blocking(get_saved_routers, active_only=True)
    if not routers:
        return

    async def _check_single(r: dict):
        if not r.get("username"):
            return

        router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
        identity = r.get("identity", router_key)

        try:
            result = await run_blocking(check_router_health, router_key)
            is_online = result["online"]
        except Exception as e:
            logger.error(f"Watchdog check failed for {router_key}: {e}")
            is_online = False

        action = record_check_result(router_key, is_online)
        if action == ALERT_WENT_OFFLINE:
            await _notify_admins(context, WATCHDOG_OFFLINE_ALERT.format(identity=identity))
            logger.warning(f"Router {identity} went offline")
        elif action == ALERT_RECOVERED:
            await _notify_admins(context, WATCHDOG_ONLINE_ALERT.format(identity=identity))
            logger.info(f"Router {identity} recovered")

    await asyncio.gather(*[_check_single(r) for r in routers])


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a notification to all configured admins."""
    from telegram.error import RetryAfter

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, parse_mode="HTML")
        except RetryAfter as e:
            logger.warning(f"Rate limited by Telegram, waiting {e.retry_after}s for admin {admin_id}")
            await asyncio.sleep(e.retry_after)
            try:
                await context.bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception as retry_err:
                logger.error(f"Failed to notify admin {admin_id} after RetryAfter: {retry_err}")
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")
