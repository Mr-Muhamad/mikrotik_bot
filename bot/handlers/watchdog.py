import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import ROUTER_KEY_PREFIX, ADMIN_IDS, WATCHDOG_INTERVAL
from core.watchdog import (
    check_router_health, get_router_status_detail,
    record_check_result, ALERT_WENT_OFFLINE, ALERT_RECOVERED,
)
from database.models import get_saved_routers, get_last_backup
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
        await _reply(update, context, query, "❌ Job Queue غير متاح")
        return

    existing = job_queue.get_jobs_by_name(JOB_NAME)
    if existing:
        await _reply(update, context, query, "✅ مراقبة الراوترات تعمل بالفعل")
        return

    job_queue.run_repeating(
        _check_all_routers,
        interval=WATCHDOG_INTERVAL,
        first=10,
        name=JOB_NAME,
        job_kwargs={"max_instances": 1},
    )
    await _reply(update, context, query, "✅ تم بدء مراقبة الراوترات (كل 5 دقائق)")


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

    await _reply(update, context, query, "❌ تم إيقاف مراقبة الراوترات")


@admin_only
async def watchdog_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current health status of all saved routers."""
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    routers = get_saved_routers(active_only=True)
    if not routers:
        await _reply(update, context, query, "📭 لا توجد روترات محفوظة")
        return

    lines = ["📊 <b>حالة الراوترات:</b>\n"]
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
            detail_line = f"آخر اتصال: {last_ok.strftime('%Y-%m-%d %H:%M')}" if last_ok else "متصل"
        elif last_fail:
            indicator = "🔴"
            detail_line = f"آخر فشل: {last_fail.strftime('%Y-%m-%d %H:%M')}"
        else:
            indicator = "⚪"
            detail_line = "لم يتم الفحص بعد"

        lines.append(f"{indicator} <b>{display}</b> ({ip})")
        lines.append(f"   ├─ الإصدار: {version}")
        lines.append(f"   ├─ {detail_line}")
        lines.append(f"   ├─ مستخدمو Hotspot النشطون: {active_text}")
        last_backup = await run_blocking(get_last_backup, router_key)
        if last_backup:
            backup_icon = "✅" if last_backup.get("status") == "success" else "❌"
            backup_text = f"{backup_icon} {last_backup.get('backup_type')} ({last_backup.get('created_at')})"
        else:
            backup_text = "—"
        lines.append(f"   └─ آخر نسخة احتياطية: {backup_text}\n")

    await _reply(update, context, query, "\n".join(lines))


async def _reply(update, context, query, text: str):
    """Send or edit in place depending on whether triggered from a callback."""
    if query:
        await safe_edit_or_send(query, context, text)
    else:
        await send_step(update, context, text)


async def _check_all_routers(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: check all saved routers and send alerts."""
    routers = get_saved_routers(active_only=True)
    if not routers:
        return

    for r in routers:
        if not r.get("username"):
            continue

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
            await _notify_admins(context, f"🔴 الروتر <b>{identity}</b> غير متصل!")
            logger.warning(f"Router {identity} went offline")
        elif action == ALERT_RECOVERED:
            await _notify_admins(context, f"🟢 الروتر <b>{identity}</b> عاد للاتصال")
            logger.info(f"Router {identity} recovered")


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a notification to all configured admins."""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")
