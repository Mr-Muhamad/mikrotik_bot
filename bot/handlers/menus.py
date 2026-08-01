"""Menu navigation handlers.

Extracted from ``bot.handlers.common`` to separate menu rendering concerns
(hotspot/userman/stats/backup/routers/reports/pdf/main menus and conversation
end-to-menu transitions) from the core command handlers and shared helpers.

These handlers render Telegram inline menus by delegating formatting to the
shared ``_show_menu`` helper kept in ``bot.handlers.common``.
"""

import logging
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# Shared helpers kept in ``common`` to avoid a circular import between
# ``menus`` and ``commands_basic`` (both depend on these primitives).
from bot.handlers.common import get_router_part, show_menu
from bot.handlers.router_system import get_router_system_part as _get_router_system_part
from bot.handlers.routers import saved_routers_list as sr
from bot.keyboards import (
    get_backup_keyboard,
    get_hotspot_keyboard,
    get_main_keyboard,
    get_pdf_settings_keyboard,
    get_reports_keyboard,
    get_routers_keyboard,
    get_stats_keyboard,
    get_userman_keyboard,
)
from bot.messages import (
    BACKUP_MENU,
    HOTSPOT_MENU,
    MAIN_MENU,
    PDF_SETTINGS_MENU,
    REPORTS_MENU,
    ROUTERS_MENU,
    STATS_MENU,
    USERMAN_MENU,
)
from bot.router_selector import cleanup_state, get_selected_router, nav_get
from utils.admin_decorator import admin_only
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_and_track

logger = logging.getLogger(__name__)


# ─── INTERNAL MENU FUNCTIONS (no @admin_only) ──────────────
# These are used by cancel/go_back handlers to avoid rate limiter conflicts.


async def internal_hotspot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, HOTSPOT_MENU, get_hotspot_keyboard)


async def internal_userman_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, USERMAN_MENU, get_userman_keyboard)


async def internal_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, STATS_MENU, get_stats_keyboard)


async def internal_backup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, BACKUP_MENU, get_backup_keyboard)


async def internal_routers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, ROUTERS_MENU, get_routers_keyboard)


async def internal_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, REPORTS_MENU, get_reports_keyboard)


async def internal_pdf_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await safe_answer_callback(query)
    await safe_edit_or_send(query, context, PDF_SETTINGS_MENU, get_pdf_settings_keyboard())


async def internal_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await get_router_part(router_key)
    system_part = await _get_router_system_part(router_key)
    text = MAIN_MENU.format(admin_name=admin_name, router_part=router_part, system_part=system_part)
    if query:
        await safe_edit_or_send(query, context, text, get_main_keyboard())
    else:
        await send_and_track(context, update.effective_chat.id, text, get_main_keyboard())


# ─── EXTERNAL MENU HANDLERS (with @admin_only) ─────────────
# These are registered as standalone handlers in main.py.


@admin_only
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the main menu with admin name and router info.

    Args:
        update: Callback query or message triggering the menu.
        context: Conversation context.

    Returns:
        ConversationHandler.END.
    """
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await get_router_part(router_key)
    system_part = await _get_router_system_part(router_key)
    text = MAIN_MENU.format(admin_name=admin_name, router_part=router_part, system_part=system_part)

    if query:
        await safe_edit_or_send(query, context, text, get_main_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=get_main_keyboard())

    return ConversationHandler.END


@admin_only
async def hotspot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the Hotspot management menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    await show_menu(update, context, HOTSPOT_MENU, get_hotspot_keyboard)


@admin_only
async def userman_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the User Manager menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    await show_menu(update, context, USERMAN_MENU, get_userman_keyboard)


@admin_only
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the statistics menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    await show_menu(update, context, STATS_MENU, get_stats_keyboard)


@admin_only
async def backup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the backup operations menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    await show_menu(update, context, BACKUP_MENU, get_backup_keyboard)


@admin_only
async def pdf_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the PDF settings menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await safe_edit_or_send(query, context, PDF_SETTINGS_MENU, get_pdf_settings_keyboard())
    else:
        await send_and_track(
            context,
            update.effective_chat.id,
            PDF_SETTINGS_MENU,
            get_pdf_settings_keyboard(),
        )


@admin_only
async def routers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the router management submenu (discover / saved / manual add)."""
    await show_menu(update, context, ROUTERS_MENU, get_routers_keyboard)


@admin_only
async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the reports menu.

    Args:
        update: Callback query from menu navigation.
        context: Conversation context.

    Returns:
        None.
    """
    await show_menu(update, context, REPORTS_MENU, get_reports_keyboard)


# ─── CONVERSATION MANAGEMENT ────────────────────────────────


@admin_only
async def menu_userman_from_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to User Manager menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_userman")


@admin_only
async def end_conversation_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to main menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "main_menu")


@admin_only
async def end_conversation_to_hotspot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to Hotspot menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_hotspot")


@admin_only
async def end_conversation_to_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to stats menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_stats")


@admin_only
async def end_conversation_to_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to backup menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_backup")


@admin_only
async def end_conversation_to_pdf_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to PDF settings menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_pdf_settings")


@admin_only
async def end_conversation_to_routers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to routers menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_routers")


@admin_only
async def end_conversation_to_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation and navigate to reports menu.

    Args:
        update: Callback query from cancel button.
        context: Conversation context to clean up.

    Returns:
        ConversationHandler.END.
    """
    return await end_conversation(update, context, "menu_reports")


# ─── NAV RESOLUTION ─────────────────────────────────────────


NAV_TARGETS: dict[str, Callable[..., Awaitable[object]]] = {
    "main_menu": internal_main_menu,
    "menu_hotspot": internal_hotspot_menu,
    "menu_userman": internal_userman_menu,
    "menu_stats": internal_stats_menu,
    "menu_backup": internal_backup_menu,
    "menu_pdf_settings": internal_pdf_settings_menu,
    "menu_routers": internal_routers_menu,
    "menu_reports": internal_reports_menu,
}


async def end_conversation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target: str = "main_menu",
) -> int:
    """Clean state and render a target menu, ending the conversation.

    Args:
        update: Callback or message triggering navigation.
        context: Conversation context to clean up.
        target: NAV_TARGETS key for the destination menu.

    Returns:
        ConversationHandler.END.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    cleanup_state(query.from_user.id, context.user_data)
    handler = NAV_TARGETS[target]
    await handler(update, context)
    return ConversationHandler.END


def resolve_nav_target(target: str) -> Callable[..., Awaitable[object]]:
    handler = NAV_TARGETS.get(target)
    if handler is not None:
        return handler
    if target == "saved_routers":
        return sr
    return internal_main_menu


@admin_only
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate to the previous menu based on saved nav state.

    Args:
        update: Callback query from back button.
        context: Conversation context with nav_back in user_data.

    Returns:
        ConversationHandler.END.
    """
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
    try:
        cleanup_state(update.effective_user.id, context.user_data)
        target = nav_get(context)
        handler = resolve_nav_target(target)
        await handler(update, context)
    except Exception as e:  # noqa: BLE001 - catch-all: navigation errors fall back to main menu safely
        logger.error("go_back navigation error: %s", e, exc_info=True)
        await internal_main_menu(update, context)
    return ConversationHandler.END
