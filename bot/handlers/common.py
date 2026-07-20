"""Shared helper primitives for menu rendering and router-name formatting.

This module intentionally keeps only the two cross-cutting helpers that both
``bot.handlers.menus`` and ``bot.handlers.commands_basic`` depend on. Keeping
them here avoids a circular import between those two sibling modules.

Previously this file was a "god-object" holding all commands, menus, navigation
and error handlers. Those have been split into:

- ``bot.handlers.commands_basic`` — /start, /help, /cancel, /clean, /sync,
  /metrics, router-selection, error_handler and reprompts.
- ``bot.handlers.menus`` — all menu handlers, end-conversation transitions,
  NAV_TARGETS, _resolve_nav_target, _end_conversation and go_back.
- ``bot.handlers.router_system`` — system-info probe/cache.

Only ``_get_router_part`` and ``_show_menu`` remain here on purpose.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.exceptions import RouterNotFoundError
from core.mikrotik_api import mikrotik_api
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import safe_edit_or_send, send_and_track
from bot.router_selector import get_selected_router

logger = logging.getLogger(__name__)


async def _get_router_part(router_key: str | None, fmt: str = "\n📡 {}") -> str:
    """Return a formatted router name string, or empty string if unavailable."""
    if not router_key:
        return ""
    try:
        name = await run_blocking(mikrotik_api.get_router_name, router_key)
        return fmt.format(name) if name else ""
    except RouterNotFoundError as e:
        logger.warning(f"Router not found while getting name for {router_key}: {e}")
        return ""
    except Exception:
        return ""


async def _show_menu(update, context, menu_text, keyboard_func):
    """Render a Telegram inline menu via callback or command invocation.

    Shared by ``bot.handlers.menus`` (all ``*_menu`` handlers) and indirectly by
    ``bot.handlers.commands_basic`` (through cancel/go_back navigation). Kept
    here so neither sibling module has to import the other for this primitive.
    """
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
    user_id = update.effective_user.id
    router_key = get_selected_router(user_id)
    admin_name = update.effective_user.full_name
    router_part = await _get_router_part(router_key)

    text = menu_text.format(admin_name=admin_name, router_part=router_part)

    if query:
        await safe_edit_or_send(query, context, text, keyboard_func())
    else:
        # Command invocation (e.g. /routers)
        await send_and_track(context, update.effective_chat.id, text, keyboard_func())