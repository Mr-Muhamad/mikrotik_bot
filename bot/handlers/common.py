import logging
from collections.abc import Callable

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.router_selector import get_selected_router
from core.exceptions import RouterNotFoundError
from core.mikrotik_api import mikrotik_api
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_and_track

logger = logging.getLogger(__name__)


async def get_router_part(router_key: str | None, fmt: str = "\n📡 {}") -> str:
    if not router_key:
        return ""
    try:
        name = await run_blocking(mikrotik_api.get_router_name, router_key)
        return fmt.format(name) if name else ""
    except RouterNotFoundError as e:
        logger.warning("Router not found while getting name for %s: %s", router_key, e)
        return ""
    except (OSError, ValueError):
        return ""


async def show_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    menu_text: str,
    keyboard_func: Callable[[], InlineKeyboardMarkup],
) -> None:
    """Render a menu by editing the current message or sending a new one.

    Args:
        update: Callback or message triggering the menu.
        context: Conversation context.
        menu_text: Formatted menu text template (uses admin_name, router_part).
        keyboard_func: Callable returning the InlineKeyboardMarkup.
    """
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await get_router_part(router_key)

    text = menu_text.format(admin_name=admin_name, router_part=router_part)

    if query:
        await safe_edit_or_send(query, context, text, keyboard_func())
    else:
        await send_and_track(context, update.effective_chat.id, text, keyboard_func())
