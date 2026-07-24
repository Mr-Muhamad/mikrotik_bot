"""Basic command handlers and conversation error handlers.

Extracted from ``bot.handlers.common`` to separate top-level Telegram commands
(/start, /help, /cancel, /clean, /sync, /metrics) and conversation control
handlers (router selection, error handler, reprompts) from menu rendering
and shared helpers.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# Shared helpers kept in ``common`` to avoid a circular import between
# ``menus`` and ``commands_basic`` (both depend on these primitives).
from bot.handlers.common import get_router_part as _get_router_part
from bot.handlers.constants import (
    WAITING_CARD_PROFILE,
    WAITING_CARD_TYPE,
    WAITING_DELETE_SELECT,
)
from bot.handlers.menus import resolve_nav_target as _resolve_nav_target
from bot.handlers.router_system import get_router_system_part as _get_router_system_part
from bot.keyboards import get_main_keyboard, get_router_keyboard
from bot.messages import (
    CLEAN_DONE,
    HELP,
    MAIN_MENU,
    METRICS_ACTIVE,
    METRICS_CACHE,
    METRICS_FAILED,
    METRICS_HEADER,
    METRICS_SERVER_HEALTH,
    METRICS_STALE,
    METRICS_SUCCESS,
    METRICS_TOTAL,
    SELECT_ROUTER,
    SYNC_COMMANDS_DONE,
    WELCOME,
)
from bot.router_selector import (
    cleanup_state,
    clear_action,
    clear_router,
    get_selected_router,
    set_current_action,
)
from core.mikrotik_api import mikrotik_api
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.bot_commands import set_bot_commands
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import (
    clean_chat_messages,
    delete_now,
    safe_edit_or_send,
    schedule_delete,
    send_and_track,
    send_step,
)

logger = logging.getLogger(__name__)


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.message:
        await delete_now(context, chat_id, update.message.message_id)

    router_key = get_selected_router(user_id)
    if router_key:
        cleanup_state(user_id, context.user_data)
        from bot.router_selector import fast_reachability_check

        if await fast_reachability_check(router_key):
            router_part = await _get_router_part(router_key)
            system_part = await _get_router_system_part(router_key)
            text = MAIN_MENU.format(
                admin_name=update.effective_user.full_name,
                router_part=router_part,
                system_part=system_part,
            )
            await send_and_track(
                context,
                chat_id,
                text,
                get_main_keyboard(),
            )
            return ConversationHandler.END

        # الراوتر المختار غير متصل أو مطفأ — التوجيه لشاشة اختيار الأجهزة مع رسالة عربية مبسطة
        offline_msg = (
            f"👋 أهلاً بك <b>{update.effective_user.full_name}</b>!\n\n"
            "⚠️ <b>تنبيه:</b> الراوتر المختار حالياً مطفأ أو غير متصل بالشبكة.\n"
            "يرجى اختيار راوتر آخر أو إضافة راوتر جديد للمتابعة:"
        )
        await send_and_track(
            context,
            chat_id,
            offline_msg,
            get_router_keyboard(),
        )
        return ConversationHandler.END

    # لا يوجد روتر — إعادة الضبط الكامل وعرض اختيار الروتر
    clear_router(user_id)
    context.user_data.clear()
    await clean_chat_messages(context, chat_id)
    await send_and_track(
        context,
        chat_id,
        WELCOME.format(admin_name=update.effective_user.full_name),
        get_router_keyboard(),
    )
    set_current_action(user_id, "start")
    return ConversationHandler.END


# ─── ROUTER SELECTION ────────────────────────────────────────


@admin_only
async def select_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    clear_router(update.effective_user.id)
    context.user_data.clear()
    await safe_edit_or_send(
        query,
        context,
        WELCOME.format(admin_name=update.effective_user.full_name),
        get_router_keyboard(),
    )
    return ConversationHandler.END


# ─── CANCEL ──────────────────────────────────────────────────


@admin_only
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nav_target = context.user_data.get("nav_back")
    clear_action(update.effective_user.id)
    chat_id = update.effective_chat.id
    last_msg_id = context.user_data.pop("last_msg", None)
    cleanup_state(update.effective_user.id, context.user_data)

    if nav_target and update.callback_query:
        handler = _resolve_nav_target(nav_target)
        await handler(update, context)
        return ConversationHandler.END

    router_key = get_selected_router(update.effective_user.id)
    admin_name = update.effective_user.full_name or update.effective_user.username or "مشرف"
    router_part = await _get_router_part(router_key, fmt=" | 🌐 {}")
    system_part = await _get_router_system_part(router_key)

    if update.callback_query:
        await safe_answer_callback(update.callback_query)
        if router_key:
            await safe_edit_or_send(
                update.callback_query,
                context,
                MAIN_MENU.format(
                    admin_name=admin_name,
                    router_part=router_part,
                    system_part=system_part,
                ),
                get_main_keyboard(),
            )
        else:
            await safe_edit_or_send(
                update.callback_query,
                context,
                SELECT_ROUTER,
                get_router_keyboard(),
            )
    else:
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Failed to delete user message: {e}")
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
            except Exception as e:
                logger.debug(f"Failed to delete last message {last_msg_id}: {e}")
        if router_key:
            await send_and_track(
                context,
                chat_id,
                MAIN_MENU.format(
                    admin_name=admin_name,
                    router_part=router_part,
                    system_part=system_part,
                ),
                get_main_keyboard(),
            )
        else:
            await send_and_track(context, chat_id, SELECT_ROUTER, get_router_keyboard())

    return ConversationHandler.END


# ─── ERROR & HELP ────────────────────────────────────────────


_NON_CRITICAL = (
    "Message is not modified",
    "Query is too old",
    "query id is invalid",
    "Message to edit not found",
    "httpx.ReadError",
    "httpx.RemoteProtocolError",
)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler — filters non-critical Telegram errors."""
    error = context.error
    error_msg = str(error) if error else ""

    if any(msg in error_msg for msg in _NON_CRITICAL):
        logger.debug(f"Non-critical Telegram error ignored: {error_msg}")
        return

    logger.exception(f"Unhandled error: {error}")
    if update and update.effective_chat:
        try:
            await send_and_track(
                context,
                update.effective_chat.id,
                "❌ حدث خطأ غير متوقع.\nاستخدم /cancel للخروج من الوضع الحالي\nأو /start للعودة للقائمة.",  # noqa: E501
            )
        except Exception as e:
            logger.debug(f"Failed to send error message: {e}")
    elif error:
        try:
            from config import ADMIN_IDS

            if ADMIN_IDS and ADMIN_IDS[0]:
                admin_id = ADMIN_IDS[0]
                from utils.error_response import sanitize_error_text

                clean_text = sanitize_error_text(str(error)[:300])
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ <b>تنبيه نظام:</b> حدث خطأ غير متوقع في مهمة خلفية:\n<code>{clean_text}</code>",
                    parse_mode="HTML",
                )
        except Exception as send_admin_err:
            logger.debug(f"Failed to notify admin of background error: {send_admin_err}")

    if update and update.effective_user:
        clear_action(update.effective_user.id)
        cleanup_state(update.effective_user.id, context.user_data)


@admin_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await send_and_track(context, chat_id, HELP, parse_mode="HTML")
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete help command message: {e}")


# ─── CLEAN CHAT ──────────────────────────────────────────────


@admin_only
async def clean_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await clean_chat_messages(context, chat_id)
    if update.message:
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Failed to delete clean command message: {e}")
    msg = await context.bot.send_message(chat_id, CLEAN_DONE)
    await schedule_delete(context, chat_id, msg.message_id, 3)


# ─── SYNC COMMANDS ──────────────────────────────────────────


@admin_only
async def sync_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual retry of set_bot_commands — useful if menu didn't load at startup."""
    await set_bot_commands(context.application)
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id, SYNC_COMMANDS_DONE)
    await schedule_delete(context, chat_id, msg.message_id, 5)
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete sync command message: {e}")


# ─── METRICS ───────────────────────────────────────────────


@admin_only
async def metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    metrics = await run_blocking(mikrotik_api.get_metrics)
    total = metrics.get("total_attempts", 0)
    success = metrics.get("successful", 0)
    failed = metrics.get("failed", 0)
    rate = (success * 100 // total) if total > 0 else 0

    server_health_text = ""
    try:
        import os
        import time
        from datetime import timedelta

        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        ram_total_gb = ram.total / (1024**3)
        ram_used_gb = ram.used / (1024**3)
        ram_percent = ram.percent

        process = psutil.Process(os.getpid())
        bot_ram_mb = process.memory_info().rss / (1024**2)
        bot_uptime_seconds = time.time() - process.create_time()
        bot_uptime_str = str(timedelta(seconds=int(bot_uptime_seconds)))

        server_health_text = METRICS_SERVER_HEALTH.format(
            cpu=cpu_percent,
            ram_used=ram_used_gb,
            ram_total=ram_total_gb,
            ram_percent=ram_percent,
            bot_ram=bot_ram_mb,
            bot_uptime=bot_uptime_str,
        )
    except ImportError:
        logger.warning("psutil is not installed. Server health metrics disabled.")
    except Exception as e:
        logger.error(f"Failed to fetch system metrics: {e}")

    text = (
        METRICS_HEADER
        + METRICS_ACTIVE.format(active=metrics.get("active_connections", 0))
        + "\n"
        + METRICS_STALE.format(stale=metrics.get("stale_connections", 0))
        + "\n"
        + METRICS_TOTAL.format(total=total)
        + "\n"
        + METRICS_SUCCESS.format(success=success)
        + "\n"
        + METRICS_FAILED.format(failed=failed)
        + "\n"
        + METRICS_CACHE.format(cache_hits=metrics.get("cache_hits", 0))
        + "\n"
        + f"📈 نسبة النجاح: {rate}%\n"
        + server_health_text
    )
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id, text, parse_mode="HTML")
    if update.message:
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Failed to delete metrics command message: {e}")
    await schedule_delete(context, chat_id, msg.message_id, 30)


# ─── REPROMPTS (conversation guards) ───────────────────────


@admin_only
async def reprompt_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_step(update, context, "❌ الرجاء اختيار مستخدم من الأزرار أعلاه.")
    return WAITING_DELETE_SELECT


@admin_only
async def reprompt_card_type_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_step(update, context, "❌ الرجاء اختيار نوع الكروت من الأزرار (1 أو 2 أو 3).")
    return WAITING_CARD_TYPE


@admin_only
async def reprompt_card_profile_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_step(update, context, "❌ الرجاء اختيار البروفايل من الأزرار أعلاه.")
    return WAITING_CARD_PROFILE
