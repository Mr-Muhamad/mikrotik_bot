import logging
import os

import telegram.error
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.handler_utils import get_query_message
from bot.keyboards import (
    get_backup_download_keyboard,
    get_backup_keyboard,
    get_nav_back_keyboard,
    get_schedule_keyboard,
)
from bot.messages import (
    BACKUP_ALREADY_IN_PROGRESS,
    BACKUP_BACKGROUND_NOTIFY,
    BACKUP_DL_DOWNLOAD_HINT,
    BACKUP_DL_INVALID_LINK,
    BACKUP_DL_NOT_LOCAL,
    BACKUP_DL_SEND_FAIL,
    BACKUP_DL_SEND_SUCCESS,
    BACKUP_DL_TOO_LARGE,
    BACKUP_DL_UNKNOWN_TYPE,
    BACKUP_DOWNLOADED_LOCAL,
    BACKUP_ERROR_UNEXPECTED,
    BACKUP_FAILED_FULL,
    BACKUP_FAILED_USERMAN,
    BACKUP_FULL_IN_PROGRESS,
    BACKUP_ONLY_ON_ROUTER,
    BACKUP_SUCCESS_FULL,
    BACKUP_SUCCESS_USERMAN,
    BACKUP_USERMAN_IN_PROGRESS,
    INVALID_TIME_FORMAT,
    SCHEDULE_DISABLED,
    SCHEDULE_ENABLED,
    SCHEDULE_ERROR,
    SCHEDULE_MENU,
    SCHEDULE_REMOVED,
    SCHEDULE_SET,
    SCHEDULE_TIME_LINE,
    SCHEDULE_TIME_LINE_EMPTY,
    SCHEDULE_TIME_PROMPT,
)
from bot.router_selector import cleanup_state, nav_set, set_current_action
from core.backup.files import resolve_local_backup_file
from core.backup_scheduler import backup_scheduler
from core.backup_service import backup_service
from database.models import get_backup_schedule, log_action, record_backup_result
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import is_duplicate_callback, safe_answer_callback
from utils.chat_cleaner import reply_final, send_step
from utils.error_response import send_error

from .constants import WAITING_SCHEDULE_TIME

logger = logging.getLogger(__name__)


# ─── BACKUP OPERATIONS ────────────────────────────────────────


_BACKUP_LOCKS: dict[str, bool] = {}


def _is_backup_running(router_key: str) -> bool:
    return _BACKUP_LOCKS.get(router_key, False)


def _set_backup_running(router_key: str, state: bool):
    if state:
        _BACKUP_LOCKS[router_key] = True
    else:
        _BACKUP_LOCKS.pop(router_key, None)


async def _background_backup_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    from typing import cast

    job_data = cast("dict[str, object]", job.data)
    router_key = str(job_data["router_key"])
    chat_id = int(job_data["chat_id"])  # type: ignore[arg-type]
    user_id = int(job_data["user_id"])  # type: ignore[arg-type]
    b_type = str(job_data["type"])

    logger.info(f"Starting background {b_type} backup for router {router_key} (user={user_id})")

    try:
        if b_type == "full":
            result = await run_blocking(backup_service.full_backup, router_key)
            await run_blocking(log_action, "full_backup", "", router_key, user_id)
            await run_blocking(
                record_backup_result,
                router_key,
                "full",
                result["success"],
                result.get("message", ""),
                file_name=result.get("local_path", ""),
            )
            if result["success"]:
                downloaded_raw = result.get("downloaded", [])
                downloaded = cast(list[str], downloaded_raw)
                created_files = cast(list[str], result.get("created_files", []))
                local_path = str(result.get("local_path", ""))
                warning = str(result.get("warning", ""))

                lines = [BACKUP_SUCCESS_FULL.format(message=result["message"])]
                if downloaded:
                    lines.append(BACKUP_DOWNLOADED_LOCAL.format(count=len(downloaded)))
                if warning:
                    lines.append(warning)
                if not downloaded and created_files:
                    lines.append(BACKUP_ONLY_ON_ROUTER)

                text = "\n".join(lines)

                user_data = context.application.user_data
                if user_id in user_data:
                    user_data[user_id]["backup_downloaded_list"] = downloaded or created_files
                    user_data[user_id]["backup_local_path"] = local_path

                reply_markup = None
                if downloaded or created_files:
                    text += BACKUP_DL_DOWNLOAD_HINT
                    reply_markup = get_backup_download_keyboard(
                        downloaded or created_files, "full", local_path
                    )

                await context.bot.send_message(
                    chat_id=chat_id, text=text, reply_markup=reply_markup
                )
                logger.info(f"Background full backup succeeded for router {router_key}")
            else:
                await context.bot.send_message(
                    chat_id=chat_id, text=BACKUP_FAILED_FULL.format(message=result["message"])
                )
                logger.warning(f"Background full backup failed for router {router_key}: {result.get('message')}")

        elif b_type == "userman":
            result = await run_blocking(backup_service.userman_backup, router_key)
            await run_blocking(log_action, "userman_backup", "", router_key, user_id)
            await run_blocking(
                record_backup_result,
                router_key,
                "userman",
                result["success"],
                result.get("message", ""),
                file_name=result.get("filename", ""),
            )
            if result["success"]:
                downloaded_raw = result.get("downloaded", [])
                downloaded = cast(list[str], downloaded_raw)
                created_files = cast(list[str], result.get("created_files", []))
                local_path = str(result.get("local_path", ""))
                warning = str(result.get("warning", ""))
                filename = result.get("filename", "backup.tar")

                lines = [
                    BACKUP_SUCCESS_USERMAN.format(message=result["message"]),
                    f"📦 {filename}",
                ]
                if warning:
                    lines.append(warning)

                text = "\n".join(lines)

                user_data = context.application.user_data
                if user_id in user_data:
                    user_data[user_id]["backup_downloaded_list"] = downloaded or created_files
                    user_data[user_id]["backup_local_path"] = local_path

                reply_markup = None
                if downloaded or created_files:
                    text += BACKUP_DL_DOWNLOAD_HINT
                    reply_markup = get_backup_download_keyboard(
                        downloaded or created_files, "userman", local_path
                    )

                await context.bot.send_message(
                    chat_id=chat_id, text=text, reply_markup=reply_markup
                )
                logger.info(f"Background userman backup succeeded for router {router_key}")
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=BACKUP_FAILED_USERMAN.format(message=result["message"]),
                )
                logger.warning(f"Background userman backup failed for router {router_key}: {result.get('message')}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Background backup failed for {router_key}: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=BACKUP_ERROR_UNEXPECTED.format(router_key=router_key),
            )
        except telegram.error.TelegramError:
            pass
    finally:
        _set_backup_running(router_key, False)


@admin_only
@require_role("operator")
async def backup_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue a full system backup as a background job.

    Args:
        update: Callback query from backup menu button.
        context: Context with router_key in user_data and job_queue.

    Returns:
        None.
    """
    query = update.callback_query
    if query is not None and is_duplicate_callback(query.data, update.effective_user.id):
        return
    await safe_answer_callback(query)
    if query is None:
        return
    router_key = context.user_data.get("router_key")
    if not router_key:
        await query.edit_message_text(
            BACKUP_ONLY_ON_ROUTER,
            reply_markup=get_backup_keyboard(),
        )
        return

    if _is_backup_running(router_key):
        await query.edit_message_text(
            BACKUP_ALREADY_IN_PROGRESS,
            reply_markup=get_backup_keyboard(),
        )
        return

    await query.edit_message_text(
        BACKUP_BACKGROUND_NOTIFY.format(msg=BACKUP_FULL_IN_PROGRESS),
        reply_markup=get_backup_keyboard(),
    )

    _set_backup_running(router_key, True)
    context.job_queue.run_once(
        _background_backup_job,
        when=1,
        data={
            "router_key": router_key,
            "user_id": update.effective_user.id,
            "chat_id": update.effective_chat.id,
            "type": "full",
        },
    )


@admin_only
@require_role("operator")
async def backup_userman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue a User Manager backup as a background job.

    Args:
        update: Callback query from backup menu button.
        context: Context with router_key in user_data and job_queue.

    Returns:
        None.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data.get("router_key")
    if not router_key:
        await query.edit_message_text(
            BACKUP_ONLY_ON_ROUTER,
            reply_markup=get_backup_keyboard(),
        )
        return

    if _is_backup_running(router_key):
        await query.edit_message_text(
            BACKUP_ALREADY_IN_PROGRESS,
            reply_markup=get_backup_keyboard(),
        )
        return

    await query.edit_message_text(
        BACKUP_BACKGROUND_NOTIFY.format(msg=BACKUP_USERMAN_IN_PROGRESS),
        reply_markup=get_backup_keyboard(),
    )

    _set_backup_running(router_key, True)
    context.job_queue.run_once(
        _background_backup_job,
        when=1,
        data={
            "router_key": router_key,
            "user_id": update.effective_user.id,
            "chat_id": update.effective_chat.id,
            "type": "userman",
        },
    )


# ─── SCHEDULE MANAGEMENT ──────────────────────────────────────


@admin_only
async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display current backup schedule status and controls.

    Args:
        update: Callback query from backup menu.
        context: Context with job_queue for scheduler state check.

    Returns:
        None.
    """
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
    """Clean state and navigate to schedule menu from a conversation.

    Args:
        update: Callback or message triggering navigation.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    cleanup_state(update.effective_user.id, context.user_data)
    await schedule_menu(update, context)
    return ConversationHandler.END


@require_role("operator")
@admin_only
async def schedule_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to enter a daily backup time (HH:MM).

    Args:
        update: Callback query from schedule menu.
        context: Conversation context for state management.

    Returns:
        WAITING_SCHEDULE_TIME state constant.
    """
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
    """Parse HH:MM input and start daily backup scheduler.

    Args:
        update: Message with time text (HH:MM format).
        context: Conversation context with job_queue.

    Returns:
        WAITING_SCHEDULE_TIME on error, ConversationHandler.END on success.
    """
    time_str = update.message.text.strip()
    try:
        hour, minute = time_str.split(":")
        h, m = int(hour), int(minute)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        if not context.job_queue:
            raise RuntimeError("JobQueue not available")
        backup_scheduler.start_daily(context.job_queue, h, m)
        await run_blocking(
            log_action,
            "schedule_backup",
            f"daily {time_str}",
            "",
            update.effective_user.id,
        )
        await reply_final(update, context, SCHEDULE_SET, get_backup_keyboard())
    except (ValueError, RuntimeError, OSError) as e:
        await send_error(
            update,
            context,
            e,
            log_extra="schedule_set",
        )
        await send_step(update, context, SCHEDULE_ERROR.format(INVALID_TIME_FORMAT))
        return WAITING_SCHEDULE_TIME
    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
@require_role("operator")
async def schedule_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the daily backup scheduler.

    Args:
        update: Callback query from schedule menu.
        context: Context with job_queue.

    Returns:
        None.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    if not context.job_queue:
        return
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
        await query.answer(BACKUP_DL_INVALID_LINK, show_alert=True)
        return

    downloaded = context.user_data.get("backup_downloaded_list", [])
    if not 0 <= idx < len(downloaded):
        await query.answer(BACKUP_DL_INVALID_LINK, show_alert=True)
        return
    fname = downloaded[idx]

    local_path = context.user_data.get("backup_local_path", "")
    try:
        if backup_type in ("full", "userman"):
            fpath = resolve_local_backup_file(local_path, fname)
        else:
            await query.answer(BACKUP_DL_UNKNOWN_TYPE, show_alert=True)
            return
    except ValueError:
        logger.warning(f"Rejected unsafe backup download filename: {fname!r}")
        await query.answer(BACKUP_DL_INVALID_LINK, show_alert=True)
        return

    if not os.path.isfile(fpath):
        await query.answer(BACKUP_DL_NOT_LOCAL, show_alert=True)
        return
    if os.path.getsize(fpath) >= 50 * 1024 * 1024:
        await query.answer(BACKUP_DL_TOO_LARGE, show_alert=True)
        return

    try:
        msg = get_query_message(query)
        if msg is None:
            await query.answer(BACKUP_DL_SEND_FAIL, show_alert=True)
            return
        with open(fpath, "rb") as f:
            await context.bot.send_document(
                chat_id=msg.chat_id,
                document=f,
                filename=fname,
                caption=f"📦 {'Full Backup' if backup_type == 'full' else 'User Manager'} — {fname}",  # noqa: E501
            )
        await query.answer(BACKUP_DL_SEND_SUCCESS, show_alert=False)
    except (telegram.error.TelegramError, OSError, ValueError) as e:
        logger.error(f"Failed to send backup file {fname}: {e}")
        await query.answer(BACKUP_DL_SEND_FAIL, show_alert=True)
