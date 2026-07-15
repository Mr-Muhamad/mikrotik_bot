import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from bot.keyboards import (
    get_router_keyboard,
    get_main_keyboard,
    get_hotspot_keyboard,
    get_userman_keyboard,
    get_stats_keyboard,
    get_backup_keyboard,
    get_pdf_settings_keyboard,
)
from bot.messages import (
    WELCOME, MAIN_MENU, SELECT_ROUTER, HELP, HOTSPOT_MENU,
    USERMAN_MENU, STATS_MENU, BACKUP_MENU, PDF_SETTINGS_MENU, CLEAN_DONE,
    SYNC_COMMANDS_DONE,
    METRICS_HEADER, METRICS_ACTIVE, METRICS_STALE, METRICS_TOTAL,
    METRICS_SUCCESS, METRICS_FAILED, METRICS_CACHE,
)
from bot.router_selector import (
    get_selected_router,
    set_current_action,
    clear_action,
    clear_router,
    nav_get,
    cleanup_state,
)
from bot.handlers.constants import WAITING_DELETE_SELECT, WAITING_CARD_TYPE, WAITING_CARD_PROFILE
from core.mikrotik_api import mikrotik_api
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.chat_cleaner import clean_chat_messages, schedule_delete, send_step, send_and_track, delete_now, safe_edit_or_send
from utils.callback_utils import safe_answer_callback
from utils.bot_commands import set_bot_commands
from bot.handlers.routers import saved_routers_list as sr

logger = logging.getLogger(__name__)


async def _get_router_part(router_key: str | None, fmt: str = "\n📡 {}") -> str:
    """Return a formatted router name string, or empty string if unavailable."""
    if not router_key:
        return ""
    try:
        name = await run_blocking(mikrotik_api.get_router_name, router_key)
        return fmt.format(name) if name else ""
    except Exception:
        return ""


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.message:
        await delete_now(context, chat_id, update.message.message_id)

    router_key = get_selected_router(user_id)
    if router_key:
        # متصل بالفعل — عرض القائمة الرئيسية بدون مسح الجلسة
        cleanup_state(user_id, context.user_data)
        
        temp_msg = await context.bot.send_message(chat_id, "⏳ جاري التحقق من حالة الاتصال بالراوتر...")
        is_healthy, reason = await run_blocking(mikrotik_api.check_connection_health, router_key)
        try:
            await context.bot.delete_message(chat_id, temp_msg.message_id)
        except:
            pass

        router_part = await _get_router_part(router_key)
        if is_healthy:
            text = MAIN_MENU.format(admin_name=update.effective_user.full_name, router_part=router_part)
        else:
            text = f"⚠️ <b>تنبيه:</b> تعذر الاتصال بالراوتر حالياً ({reason}).\n\n" + MAIN_MENU.format(admin_name=update.effective_user.full_name, router_part=router_part)

        await send_and_track(
            context, chat_id,
            text,
            get_main_keyboard(),
        )
        return ConversationHandler.END

    # لا يوجد روتر — إعادة الضبط الكامل وعرض اختيار الروتر
    clear_router(user_id)
    context.user_data.clear()
    await clean_chat_messages(context, chat_id)
    await send_and_track(
        context, chat_id,
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
        query, context,
        WELCOME.format(admin_name=update.effective_user.full_name),
        get_router_keyboard(),
    )
    return ConversationHandler.END


# ─── MAIN MENU ───────────────────────────────────────────────


@admin_only
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await _get_router_part(router_key)
    text = MAIN_MENU.format(admin_name=admin_name, router_part=router_part)

    if query:
        await safe_answer_callback(query)
        await safe_edit_or_send(query, context, text, get_main_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=get_main_keyboard())

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

    if update.callback_query:
        await safe_answer_callback(update.callback_query)
        if router_key:
            await safe_edit_or_send(
                update.callback_query, context,
                MAIN_MENU.format(admin_name=admin_name, router_part=router_part),
                get_main_keyboard(),
            )
        else:
            await safe_edit_or_send(
                update.callback_query, context,
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
                context, chat_id,
                MAIN_MENU.format(admin_name=admin_name, router_part=router_part),
                get_main_keyboard(),
            )
        else:
            await send_and_track(context, chat_id, SELECT_ROUTER, get_router_keyboard())

    return ConversationHandler.END


# ─── ERROR & HELP ────────────────────────────────────────────


_NON_CRITICAL = (
    "Message is not modified", "Query is too old", "query id is invalid",
    "Message to edit not found", "httpx.ReadError", "httpx.RemoteProtocolError",
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
                context, update.effective_chat.id,
                "❌ حدث خطأ غير متوقع.\nاستخدم /cancel للخروج من الوضع الحالي\nأو /start للعودة للقائمة.",
            )
        except Exception as e:
            logger.debug(f"Failed to send error message: {e}")
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
    text = (
        METRICS_HEADER
        + METRICS_ACTIVE.format(active=metrics.get("active_connections", 0)) + "\n"
        + METRICS_STALE.format(stale=metrics.get("stale_connections", 0)) + "\n"
        + METRICS_TOTAL.format(total=total) + "\n"
        + METRICS_SUCCESS.format(success=success) + "\n"
        + METRICS_FAILED.format(failed=failed) + "\n"
        + METRICS_CACHE.format(cache_hits=metrics.get("cache_hits", 0)) + "\n"
        + f"📈 نسبة النجاح: {rate}%"
    )
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id, text, parse_mode="HTML")
    if update.message:
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Failed to delete metrics command message: {e}")
    await schedule_delete(context, chat_id, msg.message_id, 30)


# ─── MENU NAVIGATION ────────────────────────────────────────


async def _show_menu(update, context, menu_text, keyboard_func):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    admin_name = update.effective_user.full_name
    router_part = await _get_router_part(router_key)
    await safe_edit_or_send(
        query, context,
        menu_text.format(admin_name=admin_name, router_part=router_part),
        keyboard_func(),
    )


# ─── INTERNAL MENU FUNCTIONS (no @admin_only) ──────────────
# These are used by cancel/go_back handlers to avoid rate limiter conflicts.


async def _internal_hotspot_menu(update, context):
    await _show_menu(update, context, HOTSPOT_MENU, get_hotspot_keyboard)


async def _internal_userman_menu(update, context):
    await _show_menu(update, context, USERMAN_MENU, get_userman_keyboard)


async def _internal_stats_menu(update, context):
    await _show_menu(update, context, STATS_MENU, get_stats_keyboard)


async def _internal_backup_menu(update, context):
    await _show_menu(update, context, BACKUP_MENU, get_backup_keyboard)


async def _internal_pdf_settings_menu(update, context):
    query = update.callback_query
    await safe_answer_callback(query)
    await safe_edit_or_send(query, context, PDF_SETTINGS_MENU, get_pdf_settings_keyboard())


async def _internal_main_menu(update, context):
    """Internal main_menu without @admin_only — safe for go_back/end_conversation."""
    query = update.callback_query
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await _get_router_part(router_key)
    text = MAIN_MENU.format(admin_name=admin_name, router_part=router_part)
    if query:
        await safe_answer_callback(query)
        await safe_edit_or_send(query, context, text, get_main_keyboard())
    else:
        await send_and_track(context, update.effective_chat.id, text, get_main_keyboard())


# ─── EXTERNAL MENU HANDLERS (with @admin_only) ─────────────
# These are registered as standalone handlers in main.py.


@admin_only
async def hotspot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_menu(update, context, HOTSPOT_MENU, get_hotspot_keyboard)


@admin_only
async def userman_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_menu(update, context, USERMAN_MENU, get_userman_keyboard)


@admin_only
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_menu(update, context, STATS_MENU, get_stats_keyboard)


@admin_only
async def backup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await safe_edit_or_send(query, context, BACKUP_MENU, get_backup_keyboard())
    else:
        await send_and_track(context, update.effective_chat.id, BACKUP_MENU, get_backup_keyboard())


@admin_only
async def pdf_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await safe_edit_or_send(query, context, PDF_SETTINGS_MENU, get_pdf_settings_keyboard())
    else:
        await send_and_track(context, update.effective_chat.id, PDF_SETTINGS_MENU, get_pdf_settings_keyboard())


# ─── CONVERSATION MANAGEMENT ────────────────────────────────


async def _end_conversation(update, context, target="main_menu"):
    query = update.callback_query
    await safe_answer_callback(query)
    cleanup_state(query.from_user.id, context.user_data)
    handler = NAV_TARGETS[target]
    await handler(update, context)
    return ConversationHandler.END


@admin_only
async def menu_userman_from_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "menu_userman")


@admin_only
async def end_conversation_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "main_menu")


@admin_only
async def end_conversation_to_hotspot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "menu_hotspot")


@admin_only
async def end_conversation_to_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "menu_stats")


@admin_only
async def end_conversation_to_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "menu_backup")


@admin_only
async def end_conversation_to_pdf_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _end_conversation(update, context, "menu_pdf_settings")


NAV_TARGETS = {
    "main_menu": _internal_main_menu,
    "menu_hotspot": _internal_hotspot_menu,
    "menu_userman": _internal_userman_menu,
    "menu_stats": _internal_stats_menu,
    "menu_backup": _internal_backup_menu,
    "menu_pdf_settings": _internal_pdf_settings_menu,
}


def _resolve_nav_target(target: str):
    """Resolve a navigation target by name, with lazy imports."""
    handler = NAV_TARGETS.get(target)
    if handler is not None:
        return handler
    if target == "saved_routers":
        return sr
    return _internal_main_menu


@admin_only
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    target = nav_get(context)
    handler = _resolve_nav_target(target)
    await handler(update, context)
    return ConversationHandler.END


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
