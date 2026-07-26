from __future__ import annotations

import os
from typing import cast

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    get_back_keyboard,
    get_backup_restore_keyboard,
    get_restore_confirm_keyboard,
    get_userman_restore_confirm_keyboard,
    get_userman_restore_keyboard,
)
from bot.messages import (
    BACKUP_RESTORE_AVAILABLE,
    BACKUP_RESTORE_CONFIRM,
    BACKUP_RESTORE_FAILED,
    BACKUP_RESTORE_IN_PROGRESS,
    BACKUP_RESTORE_INVALID_NAME,
    BACKUP_RESTORE_NO_BACKUPS,
    BACKUP_RESTORE_NONE,
    BACKUP_RESTORE_NOT_FOUND,
    BACKUP_RESTORE_PROFILES_COUNT,
    BACKUP_RESTORE_SKIPPED,
    BACKUP_RESTORE_SUCCESS,
    BACKUP_RESTORE_USERS_COUNT,
    ROUTER_NO_CREDENTIALS,
    USERMAN_RESTORE_CONFIRM,
    USERMAN_RESTORE_FAILED,
    USERMAN_RESTORE_IN_PROGRESS,
    USERMAN_RESTORE_MENU,
    USERMAN_RESTORE_NO_BACKUPS,
    USERMAN_RESTORE_PARTIAL,
    USERMAN_RESTORE_SUCCESS,
)
from bot.router_selector import cleanup_state, get_selected_router, nav_set
from core.backup_service import (
    backup_restore,
    backup_service,
    resolve_userman_backup_file,
)
from core.mikrotik_client import RouterOSRow
from database.models import log_action
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import edit_clean, send_step
from utils.error_response import send_error
from utils.tg_helpers import get_from_user_id


@require_role("admin")
@admin_only
async def backup_restore_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available backups on the selected router."""
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        if query:
            await query.edit_message_text(ROUTER_NO_CREDENTIALS)
        else:
            await send_step(update, context, ROUTER_NO_CREDENTIALS)
        return ConversationHandler.END

    try:
        backups = await run_blocking(backup_restore.list_router_backups, router_key)
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="backup_restore_start",
        )

        return ConversationHandler.END

    if not backups:
        text = BACKUP_RESTORE_NO_BACKUPS
        await send_step(update, context, text, get_back_keyboard("menu_backup"))
        return ConversationHandler.END

    context.user_data["restore_backup_list"] = backups
    text = BACKUP_RESTORE_AVAILABLE.format(count=len(backups))
    keyboard = get_backup_restore_keyboard(backups)
    nav_set(context, "menu_backup")
    await send_step(update, context, text, keyboard)


@require_role("admin")
@admin_only
async def backup_restore_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation dialog for selected backup."""
    query = update.callback_query
    if query is None:
        return
    await safe_answer_callback(query)

    idx = int(query.data.split(":")[-1]) if query.data else 0
    backups = context.user_data.get("restore_backup_list", [])
    backup_name = backups[idx]["name"] if 0 <= idx < len(backups) else ""
    context.user_data["restore_backup_name"] = backup_name

    text = BACKUP_RESTORE_CONFIRM.format(name=backup_name)
    keyboard = get_restore_confirm_keyboard()
    await edit_clean(query, context, text, keyboard)


@require_role("admin")
@admin_only
async def backup_restore_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute backup restore after confirmation."""
    query = update.callback_query
    if query is None:
        return
    await safe_answer_callback(query)

    backup_name = context.user_data.get("restore_backup_name", "")
    router_key = get_selected_router(get_from_user_id(query))

    if not router_key:
        await query.edit_message_text(ROUTER_NO_CREDENTIALS)
        return ConversationHandler.END

    await query.edit_message_text(BACKUP_RESTORE_IN_PROGRESS.format(name=backup_name))

    try:
        result = await run_blocking(backup_restore.restore_backup, router_key, backup_name)
        await run_blocking(
            log_action,
            "restore_backup",
            backup_name,
            router_key,
            get_from_user_id(query),
        )

        if result.get("success"):
            await query.edit_message_text(BACKUP_RESTORE_SUCCESS.format(name=backup_name))
        else:
            await query.edit_message_text(
                BACKUP_RESTORE_FAILED.format(error=result.get("message", "Unknown error"))
            )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="backup_restore_confirm",
        )

    return ConversationHandler.END


# ─── USERMAN RESTORE ───────────────────────────────────────────


@require_role("admin")
@admin_only
async def userman_restore_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List saved User Manager tar backups for restore."""
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)

    try:
        tar_files = await run_blocking(backup_service.list_local_userman_backups)
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            log_extra="userman_restore_start",
        )
        return ConversationHandler.END

    if not tar_files:
        text = USERMAN_RESTORE_NO_BACKUPS
        await send_step(update, context, text, get_back_keyboard("menu_backup"))
        return ConversationHandler.END

    context.user_data["userman_restore_list"] = tar_files
    nav_set(context, "menu_backup")
    text = USERMAN_RESTORE_MENU
    keyboard = get_userman_restore_keyboard(tar_files)
    await send_step(update, context, text, keyboard)


@require_role("admin")
@admin_only
async def userman_restore_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation dialog for selected userman backup."""
    query = update.callback_query
    if query is None:
        return
    await safe_answer_callback(query)

    idx = int(query.data.split(":")[-1]) if query.data else 0
    tar_files = context.user_data.get("userman_restore_list", [])
    tar_filename = tar_files[idx].get("filename", "") if 0 <= idx < len(tar_files) else ""
    context.user_data["userman_restore_tar"] = tar_filename

    text = USERMAN_RESTORE_CONFIRM.format(name=tar_filename)
    keyboard = get_userman_restore_confirm_keyboard()
    await edit_clean(query, context, text, keyboard)


def _format_restore_summary(result: RouterOSRow) -> str:
    """Build a human-readable summary from a userman restore result."""
    parts = []
    profiles_restored = result.get("profiles_restored")
    if profiles_restored:
        parts.append(BACKUP_RESTORE_PROFILES_COUNT.format(count=int(profiles_restored)))
    users_restored = result.get("users_restored")
    if users_restored:
        parts.append(BACKUP_RESTORE_USERS_COUNT.format(count=int(users_restored)))
    skipped_raw = result.get("skipped")
    if isinstance(skipped_raw, dict):
        skipped_dict = cast(dict[str, int], skipped_raw)
        profiles_skipped = skipped_dict.get("profiles", 0)
        users_skipped = skipped_dict.get("users", 0)
        if profiles_skipped or users_skipped:
            parts.append(BACKUP_RESTORE_SKIPPED.format(skipped=profiles_skipped + users_skipped))
    return "، ".join(parts) if parts else BACKUP_RESTORE_NONE


@require_role("admin")
@admin_only
async def userman_restore_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute User Manager restore from selected tar file."""
    query = update.callback_query
    if query is None:
        return
    await safe_answer_callback(query)

    tar_filename = context.user_data.get("userman_restore_tar", "")
    router_key = get_selected_router(get_from_user_id(query))

    if not router_key:
        await query.edit_message_text(ROUTER_NO_CREDENTIALS)
        return ConversationHandler.END

    try:
        tar_path = resolve_userman_backup_file(tar_filename)
    except ValueError:
        await query.edit_message_text(
            USERMAN_RESTORE_FAILED.format(error=BACKUP_RESTORE_INVALID_NAME)
        )
        return

    if not os.path.isfile(tar_path):
        await query.edit_message_text(USERMAN_RESTORE_FAILED.format(error=BACKUP_RESTORE_NOT_FOUND))
        return ConversationHandler.END

    await query.edit_message_text(USERMAN_RESTORE_IN_PROGRESS)

    try:
        result = await run_blocking(backup_service.userman_restore, router_key, tar_path)
        await run_blocking(
            log_action,
            "userman_restore",
            tar_filename,
            router_key,
            get_from_user_id(query),
        )

        if result["success"] and not result.get("errors"):
            summary = _format_restore_summary(result)
            await query.edit_message_text(USERMAN_RESTORE_SUCCESS.format(summary=summary))
        elif result.get("errors"):
            await query.edit_message_text(
                USERMAN_RESTORE_PARTIAL.format(summary=result.get("message", ""))
            )
        else:
            await query.edit_message_text(
                USERMAN_RESTORE_FAILED.format(error=result.get("message", "Unknown error"))
            )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="userman_restore_execute",
        )
    return ConversationHandler.END
