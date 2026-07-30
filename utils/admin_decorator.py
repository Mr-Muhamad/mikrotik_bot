import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from functools import wraps

import telegram.error
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from utils.error_response import classify_error
from utils.logging_setup import (
    bind_context,
    set_command,
    set_router_key,
)

logger = logging.getLogger(__name__)

ADMIN_ONLY_MSG = "❌ هذا البوت مخصص للأدمن فقط."

ROLE_LEVELS = {
    "super_admin": 40,
    "customer": 30,
    "admin": 30,
    "operator": 20,
    "viewer": 10,
}
ROLE_LABELS = {
    "super_admin": "👑 مدير عام",
    "customer": "🏢 عميل",
    "admin": "👑 مالك/أدمن",
    "operator": "🛠️ مشغّل",
    "viewer": "👁️ مشاهد",
}
INSUFFICIENT_ROLE_MSG = "⛔ صلاحيتك غير كافية لتنفيذ هذا الأمر."

_rate_limit_data: dict[tuple[int, str] | str, float | bool] = {}
_rate_limit_lock = threading.Lock()
_last_cleanup = time.monotonic()
_RATE_LIMIT_CLEANUP_INTERVAL = 300
_RATE_LIMIT_MAX_AGE = 60
_DEFAULT_RATE_LIMIT = 1.0
RATE_LIMIT_WINDOW = 0.5

_RATE_LIMITS: dict[str, float] = {
    "reboot": 10.0,
    "manual_add": 2.0,
    "backup": 30.0,
    "restore": 60.0,
    "delete": 5.0,
    "add": 2.0,
    "edit": 2.0,
}


def _get_rate_limit(func_name: str) -> float:
    for key, limit in _RATE_LIMITS.items():
        if key in func_name:
            return limit
    return _DEFAULT_RATE_LIMIT


def _reset_user_rate_limit(user_id: int) -> None:
    with _rate_limit_lock:
        keys_to_del = [k for k in _rate_limit_data if isinstance(k, tuple) and k[0] == user_id]
        for k in keys_to_del:
            _rate_limit_data.pop(k, None)


def reset_rate_limit(user_id: int) -> None:
    """Reset rate limit for a user — call after successful router connection."""
    _reset_user_rate_limit(user_id)



def _check_rate_limit(user_id: int, func_name: str = "") -> bool:
    if "PYTEST_CURRENT_TEST" in os.environ and not _rate_limit_data.get("_test_enforce_rate_limit"):
        return True
    global _last_cleanup
    now = time.monotonic()
    limit = _get_rate_limit(func_name)
    key = (user_id, func_name)

    with _rate_limit_lock:
        if now - _last_cleanup > _RATE_LIMIT_CLEANUP_INTERVAL:
            stale = [
                k for k, ts in list(_rate_limit_data.items()) if now - ts > _RATE_LIMIT_MAX_AGE
            ]
            for k in stale:
                del _rate_limit_data[k]
            _last_cleanup = now

        last = _rate_limit_data.get(key, 0.0)
        if now - last < limit:
            return False

        _rate_limit_data[key] = now
        return True


def _is_group_chat(update: Update) -> bool:
    chat = update.effective_chat
    if chat:
        chat_type = getattr(chat, "type", None)
        if isinstance(chat_type, str) and chat_type != "private":
            return True
    return False


async def _send_reply(update: Update, text: str):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
    elif update.message:
        await update.message.reply_text(text)


def _log_action_incoming(update: Update, router_key: str, func_name: str) -> None:
    """Log an incoming handler action for observability."""
    user_id = update.effective_user.id
    user_full_name = update.effective_user.full_name
    if update.callback_query:
        logger.info(
            "📥 [ACTION INCOMING] User: %s (%s) | Router: %s | Button: '%s' | Handler: %s",
            user_id, user_full_name, router_key,
            update.callback_query.data, func_name,
        )
    elif update.message and update.message.text:
        text_preview = update.message.text[:30] + (
            "..." if len(update.message.text) > 30 else ""
        )
        logger.info(
            "📥 [ACTION INCOMING] User: %s (%s) | Router: %s | Input: '%s' | Handler: %s",
            user_id, user_full_name, router_key, text_preview, func_name,
        )


async def _handle_rate_limited(update: Update, func_name: str) -> None:
    user_id = update.effective_user.id
    logger.warning("RATE LIMITED: User: %s | Handler: %s", user_id, func_name)
    if update.callback_query:
        try:
            await update.callback_query.answer(text="⏳", show_alert=False)
        except telegram.error.TelegramError:
            pass


async def _execute_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    func: Callable[..., Awaitable[object]],
    user_id: int,
    router_key: str,
) -> object | None:
    """Execute a decorated handler with timing, logging, and activity tracking."""
    start_time = time.perf_counter()
    try:
        res = await func(update, context)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        with bind_context(success=True, duration_ms=elapsed_ms):
            logger.info(
                "✅ [ACTION SUCCESS] User: %s | Router: %s | Handler: %s | Time: %.1fms",
                user_id, router_key, func.__name__, elapsed_ms,
            )
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        category = classify_error(e)
        with bind_context(success=False, duration_ms=elapsed_ms, error_category=category):
            logger.exception(
                "❌ [ACTION FAILED] User: %s | Router: %s | Handler: %s | Error: %s | Time: %.1fms",
                user_id, router_key, func.__name__, e, elapsed_ms,
            )
        raise
    from database.repositories.user_sessions import update_activity
    update_activity(user_id)
    return res


def _is_authorized(user_id: int) -> bool:
    """Return True if the user is a known admin (by ID or stored DB role)."""
    if user_id in ADMIN_IDS:
        return True
    from database.models import get_admin_role
    if get_admin_role(user_id):
        return True
    return False


async def _check_role_level(user_id: int, min_level: int, func_name: str, update: Update) -> bool:
    """Return True if the user meets the minimum role level. Logs and replies on failure."""
    from database.models import get_admin_role
    db_role = get_admin_role(user_id)
    if user_id not in ADMIN_IDS and db_role is None:
        logger.warning("UNAUTHORIZED ACCESS: user_id=%s, function=%s", user_id, func_name)
        await _send_reply(update, ADMIN_ONLY_MSG)
        return False
    role = "super_admin" if user_id in ADMIN_IDS else (db_role or "admin")
    if ROLE_LEVELS.get(role, 0) < min_level:
        logger.warning(
            "INSUFFICIENT ROLE: user_id=%s, role=%s, required=%s, function=%s",
            user_id, role, min_level, func_name,
        )
        await _send_reply(update, INSUFFICIENT_ROLE_MSG)
        return False
    return True


def admin_only(func: Callable[..., Awaitable[object]]):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        user_id = user.id

        if _is_group_chat(update):
            return

        from utils.request_id import request_id_scope

        rid = str(getattr(update, "update_id", None) or f"req_{int(time.time()*1000)}")

        with request_id_scope(rid):
            from bot.router_selector import get_selected_router

            router_key = get_selected_router(user_id) or "None"
            set_router_key(router_key)
            set_command(func.__name__)

            _log_action_incoming(update, router_key, func.__name__)

            if not _check_rate_limit(user_id, func.__name__):
                await _handle_rate_limited(update, func.__name__)
                return

            if not _is_authorized(user_id):
                await _send_reply(update, ADMIN_ONLY_MSG)
                return

            return await _execute_handler(update, context, func, user_id, router_key)

    return wrapper


def require_role(min_role: str):
    """Allow only admins whose role level meets the requested minimum.

    Roles (highest to lowest): admin (30) > operator (20) > viewer (10).
    An admin without a recorded role is treated as 'admin' (full access)
    so existing deployments keep working until roles are assigned.

    Includes observability logging (📥/✅/❌), request_id correlation,
    and rate limiting so decorated handlers are fully self-contained even
    when used without @admin_only.
    """
    min_level = ROLE_LEVELS.get(min_role, 30)

    def decorator(func: Callable[..., Awaitable[object]]):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if user is None:
                return
            user_id = user.id

            if _is_group_chat(update):
                return

            from utils.request_id import request_id_scope

            rid = str(
                getattr(update, "update_id", None)
                or f"req_{int(time.time()*1000)}"
            )

            with request_id_scope(rid):
                from bot.router_selector import get_selected_router

                router_key = get_selected_router(user_id) or "None"
                set_router_key(router_key)
                set_command(func.__name__)

                _log_action_incoming(update, router_key, func.__name__)

                if not _check_rate_limit(user_id, func.__name__):
                    await _handle_rate_limited(update, func.__name__)
                    return

                if not await _check_role_level(user_id, min_level, func.__name__, update):
                    return

                return await _execute_handler(update, context, func, user_id, router_key)

        return wrapper

    return decorator
