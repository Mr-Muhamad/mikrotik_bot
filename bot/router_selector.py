from functools import wraps
import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.models import get_user_session, save_user_session
from bot.keyboards import get_router_keyboard
from bot.messages import NO_ROUTER_SELECTED

logger = logging.getLogger(__name__)

PRESERVED_USER_DATA_KEYS = {
    "nav_back",
    "router_key",
    "profile_names",
}

CONVERSATION_USER_DATA_KEYS = (
    "add_username", "add_password", "add_profile", "add_bytes", "add_uptime",
    "edit_user_id", "edit_user_data", "edit_field",
    "delete_user_id", "search_hosts", "kick_host_idx", "users_cache",
    "card_type", "card_profile", "card_payment", "card_caller_id", "pdf_option",
    "disc_ip", "disc_username", "disc_router_id",
    "rename_router_id", "last_msg",
    "hs_card_count", "hs_card_length", "hs_card_prefix",
    "hs_card_system", "hs_card_profile", "hs_card_uptime",
    "hs_card_bytes", "hs_uptime_unit", "uptime_unit",
    "usage_router",
    "backup_local_path", "backup_downloaded", "backup_type",
    "backup_downloaded_list",
    "restore_backup_list", "restore_backup_name",
    "userman_restore_list", "userman_restore_tar",
)


def get_selected_router(user_id):
    """Return the currently selected router key for a user, or None."""
    session = get_user_session(user_id)
    selected_router = session.get("selected_router") if session else None
    return selected_router


def set_selected_router(user_id, router_key):
    """Set the selected router key for a user in the database."""
    save_user_session(user_id, selected_router=router_key)


def set_current_action(user_id, action, data=None):
    """Set the current in-progress action and optional data for a user."""
    save_user_session(user_id, current_action=action, action_data=data)


def clear_action(user_id):
    """Clear the current action for a user while preserving selected router."""
    save_user_session(user_id, current_action=None, action_data=None)


def clear_router(user_id):
    """Clear all session state for a user (router selection and current action)."""
    save_user_session(user_id, selected_router="", current_action=None, action_data=None)


def nav_set(context, back_to):
    """Set the navigation back target in user_data for the current conversation."""
    context.user_data["nav_back"] = back_to


def nav_get(context):
    """Return the current navigation back target, defaulting to main_menu."""
    return context.user_data.get("nav_back", "main_menu")


def cleanup_state(user_id, user_data):
    """Clear the user's database action state and conversation-specific user_data keys.
    
    Preserves nav_back, router_key, and profile_names to maintain navigation state.
    """
    clear_action(user_id)
    for key in CONVERSATION_USER_DATA_KEYS:
        user_data.pop(key, None)


def require_router(func):
    """Ensure a router is selected before running a handler.

    Lives in the bot (presentation) layer because it depends on presentation
    concerns (keyboards and user-facing messages). It reads the module-level
    ``get_selected_router`` so tests can monkeypatch it.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id
        router_key = get_selected_router(user_id)
        if not router_key:
            keyboard = get_router_keyboard()
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    NO_ROUTER_SELECTED, reply_markup=keyboard
                )
            elif update.message:
                await update.message.reply_text(
                    NO_ROUTER_SELECTED, reply_markup=keyboard
                )
            return
        context.user_data["router_key"] = router_key
        return await func(update, context)
    return wrapper


