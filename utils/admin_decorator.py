import logging
import threading
import time
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS

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

RATE_LIMIT_WINDOW = 1.0
RATE_LIMITS: dict[str, float] = {
    "default": 1.0,
    "reboot": 10.0,
    "backup": 30.0,
    "restore": 60.0,
    "delete": 5.0,
    "add": 2.0,
    "edit": 2.0,
}
_RATE_LIMIT_MAX_AGE = 3600
_RATE_LIMIT_CLEANUP_INTERVAL = 300.0
_rate_limit_data: dict[tuple[int, str], float] = {}
_last_cleanup: float = 0.0
_rate_limit_lock = threading.Lock()


def _get_rate_limit(func_name: str) -> float:
    for key, limit in RATE_LIMITS.items():
        if key != "default" and key in func_name.lower():
            return limit
    return RATE_LIMITS["default"]


def reset_rate_limit(user_id: int):
    """Reset rate limit for a user — call after successful router connection."""
    with _rate_limit_lock:
        keys_to_del = [k for k in _rate_limit_data if k[0] == user_id]
        for k in keys_to_del:
            _rate_limit_data.pop(k, None)


def _check_rate_limit(user_id: int, func_name: str = "") -> bool:
    global _last_cleanup
    now = time.monotonic()
    limit = _get_rate_limit(func_name)
    key = (user_id, func_name)

    with _rate_limit_lock:
        if now - _last_cleanup > _RATE_LIMIT_CLEANUP_INTERVAL:
            stale = [k for k, ts in list(_rate_limit_data.items()) if now - ts > _RATE_LIMIT_MAX_AGE]
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


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        user_id = user.id

        if _is_group_chat(update):
            return

        if user_id not in ADMIN_IDS:
            from database.models import get_admin_role

            role = get_admin_role(user_id)
            if not role:
                chat_id = update.effective_chat.id if update.effective_chat else "unknown"
                logger.warning(
                    f"UNAUTHORIZED ACCESS: user_id={user_id}, "
                    f"function={func.__name__}, "
                    f"chat_id={chat_id}"
                )
                await _send_reply(update, ADMIN_ONLY_MSG)
                return

        if not _check_rate_limit(user_id, func.__name__):
            if update.callback_query:
                try:
                    await update.callback_query.answer(text="⏳", show_alert=False)
                except Exception:
                    pass
            return

        from database.repositories.user_sessions import update_activity

        update_activity(user_id)

        return await func(update, context)

    return wrapper


def require_role(min_role: str):
    """Allow only admins whose role level meets the requested minimum.

    Roles (highest to lowest): admin (30) > operator (20) > viewer (10).
    An admin without a recorded role is treated as 'admin' (full access)
    so existing deployments keep working until roles are assigned.
    """
    min_level = ROLE_LEVELS.get(min_role, 30)

    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if user is None:
                return
            user_id = user.id

            if _is_group_chat(update):
                return

            from database.models import get_admin_role

            db_role = get_admin_role(user_id)
            if user_id not in ADMIN_IDS and db_role is None:
                logger.warning(f"UNAUTHORIZED ACCESS: user_id={user_id}, function={func.__name__}")
                await _send_reply(update, ADMIN_ONLY_MSG)
                return

            role = "super_admin" if user_id in ADMIN_IDS else (db_role or "admin")

            if ROLE_LEVELS.get(role, 0) < min_level:
                logger.warning(
                    f"INSUFFICIENT ROLE: user_id={user_id}, role={role}, "
                    f"required={min_role}, function={func.__name__}"
                )
                await _send_reply(update, INSUFFICIENT_ROLE_MSG)
                return

            return await func(update, context)

        return wrapper

    return decorator
