import logging
import os
from telegram import Update
from utils.async_blocking import run_blocking
from telegram.ext import ContextTypes, ConversationHandler
from bot.keyboards import (
    get_backup_keyboard,
    get_schedule_keyboard,
    get_nav_back_keyboard,
    get_backup_download_keyboard,
)
from bot.messages import (
    SCHEDULE_ENABLED, SCHEDULE_DISABLED,
    SCHEDULE_MENU, SCHEDULE_TIME_PROMPT, SCHEDULE_SET, SCHEDULE_ERROR,
    SCHEDULE_REMOVED, BACKUP_FULL_IN_PROGRESS, BACKUP_USERMAN_IN_PROGRESS,
    INVALID_TIME_FORMAT, SCHEDULE_TIME_LINE, SCHEDULE_TIME_LINE_EMPTY,
)
from database.models import get_backup_schedule, record_backup_result
from bot.router_selector import set_current_action, nav_set, cleanup_state, require_router
from core.backup_service import backup_service
from core.backup.files import resolve_local_backup_file, resolve_userman_backup_file
from core.backup_scheduler import backup_scheduler
from database.models import log_action
from utils.callback_utils import safe_answer_callback,is_duplicate_callback
from utils.chat_cleaner import edit_clean, send_step, reply_final
from .constants import WAITING_SCHEDULE_TIME
from utils.admin_decorator import admin_only, require_role
from utils.error_response import send_error
from config import BACKUP_DIR

logger = logging.getLogger(__name__)


# ─── BACKUP OPERATIONS ────────────────────────────────────────


@require_role("operator")
@admin_only
@require_router
async def backup_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if is_duplicate_callback(query.data, update.effective_user.id):
        return
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    await query.edit_message_text(BACKUP_FULL_IN_PROGRESS)
    try:
        result = await run_blocking(backup_service.full_backup, router_key)
        await run_blocking(log_action, "full_backup", "", router_key, query.from_user.id)
        await run_blocking(
            record_backup_result,
            router_key, "full", result["success"],
            result.get("message", ""), file_name=result.get("local_path", ""),
        )
        if result["success"]:
            downloaded = result.get("downloaded", [])
            lines = [f"✅ {result['message']}"]
            if downloaded:
                lines.append(f"📁 تم تحميل {len(downloaded)} ملف محلياً")
            else:
                lines.append("⚠️ الملفات لا تزال على الراوتر فقط")
            # تخزين المسار للتحميل الاختياري
            context.user_data["backup_local_path"] = result.get("local_path", "")
            context.user_data["backup_downloaded"] = downloaded
            context.user_data["backup_type"] = "full"
            context.user_data["backup_downloaded_list"] = downloaded
            await edit_clean(
                query, context,
                "\n".join(lines),
                get_backup_download_keyboard(downloaded, "full", result.get("local_path", "")),
            )
        else:
            await query.edit_message_text(f"❌ {result['message']}")
    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra="backup_full",
            reply_markup=get_backup_keyboard(),
        )


@require_role("operator")
@admin_only
@require_router
async def backup_userman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    await query.edit_message_text(BACKUP_USERMAN_IN_PROGRESS)
    try:
        result = await run_blocking(backup_service.userman_backup, router_key)
        await run_blocking(log_action, "userman_backup", "", router_key, query.from_user.id)
        await run_blocking(
            record_backup_result,
            router_key, "userman", result["success"],
            result.get("message", ""), file_name=result.get("filename", ""),
        )
        if result["success"]:
            filename = result.get("filename", "backup.tar")
            lines = [
                f"✅ {result['message']}",
                f"👥 المستخدمين: {result['users_count']}",
                f"📋 البروفايلات: {result['profiles_count']}",
                f"📦 {filename}",
            ]
            # تخزين المسار للتحميل الاختياري
            context.user_data["backup_local_path"] = os.path.dirname(result.get("local_path", ""))
            context.user_data["backup_downloaded"] = [filename]
            context.user_data["backup_type"] = "userman"
            context.user_data["backup_downloaded_list"] = [filename]
            await edit_clean(
                query, context,
                "\n".join(lines),
                get_backup_download_keyboard([filename], "userman", os.path.dirname(result.get("local_path", ""))),
            )
        else:
            await query.edit_message_text(f"❌ {result['message']}")
    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra="backup_userman",
            reply_markup=get_backup_keyboard(),
        )


# ─── SCHEDULE MANAGEMENT ──────────────────────────────────────


@admin_only
async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    enabled = backup_scheduler.is_running(context.job_queue)
    status = SCHEDULE_ENABLED if enabled else SCHEDULE_DISABLED
    settings = get_backup_schedule()
    if enabled:
        time_line = SCHEDULE_TIME_LINE.format(
            hour=settings["schedule_hour"], minute=settings["schedule_minute"]
        )
    else:
        time_line = SCHEDULE_TIME_LINE_EMPTY
    await query.edit_message_text(
        SCHEDULE_MENU.format(status=status, time_line=time_line),
        reply_markup=get_schedule_keyboard(),
    )


@admin_only
async def schedule_menu_from_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    await schedule_menu(update, context)
    return ConversationHandler.END


@require_role("operator")
@admin_only
async def schedule_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    cleanup_state(query.from_user.id, context.user_data)
    set_current_action(query.from_user.id, "schedule_time")
    nav_set(context, "menu_backup")
    await query.edit_message_text(SCHEDULE_TIME_PROMPT, reply_markup=get_nav_back_keyboard())
    return WAITING_SCHEDULE_TIME


@require_role("operator")
@admin_only
async def schedule_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()
    try:
        hour, minute = time_str.split(":")
        h, m = int(hour), int(minute)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        backup_scheduler.start_daily(context.job_queue, h, m)
        await run_blocking(log_action, "schedule_backup", f"daily {time_str}", "", update.effective_user.id)
        await reply_final(update, context, SCHEDULE_SET, get_backup_keyboard())
    except Exception as e:
        await send_error(
            update, context, e,
            log_extra="schedule_set",
        )
        await send_step(update, context, SCHEDULE_ERROR.format(INVALID_TIME_FORMAT))
        return WAITING_SCHEDULE_TIME
    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END


@require_role("operator")
@admin_only
async def schedule_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    backup_scheduler.stop(context.job_queue)
    await run_blocking(log_action, "disable_schedule", "", "", query.from_user.id)
    await query.edit_message_text(SCHEDULE_REMOVED, reply_markup=get_backup_keyboard())


# ─── BACKUP FILE DOWNLOAD (اختياري) ──────────────────────────


@admin_only
async def backup_download_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال ملف الباكوب عند ضغط المستخدم على زر التحميل."""
    query = update.callback_query
    await safe_answer_callback(query)
    # callback_data: backup_dl:{type}:{index}
    try:
        _, backup_type, idx_str = query.data.split(":", 2)
        idx = int(idx_str)
    except (ValueError, IndexError):
        await query.answer("⚠️ رابط تحميل غير صالح", show_alert=True)
        return

    downloaded = context.user_data.get("backup_downloaded_list", [])
    if not 0 <= idx < len(downloaded):
        await query.answer("⚠️ رابط تحميل غير صالح", show_alert=True)
        return
    fname = downloaded[idx]

    local_path = context.user_data.get("backup_local_path", "")
    try:
        if backup_type == "full":
            fpath = resolve_local_backup_file(local_path, fname)
        elif backup_type == "userman":
            fpath = resolve_userman_backup_file(fname, BACKUP_DIR)
        else:
            await query.answer("⚠️ نوع باكوب غير معروف", show_alert=True)
            return
    except ValueError:
        logger.warning(f"Rejected unsafe backup download filename: {fname!r}")
        await query.answer("⚠️ رابط تحميل غير صالح", show_alert=True)
        return

    if not os.path.isfile(fpath):
        await query.answer("⚠️ الملف غير موجود محلياً", show_alert=True)
        return
    if os.path.getsize(fpath) >= 50 * 1024 * 1024:
        await query.answer("⚠️ الملف كبير جداً للإرسال عبر تليجرام (أكبر من 50MB)", show_alert=True)
        return

    try:
        with open(fpath, "rb") as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=fname,
                caption=f"📦 {'Full Backup' if backup_type == 'full' else 'User Manager'} — {fname}",
            )
        await query.answer("✅ تم إرسال الملف", show_alert=False)
    except Exception as e:
        logger.error(f"Failed to send backup file {fname}: {e}")
        await query.answer("❌ فشل إرسال الملف", show_alert=True)
