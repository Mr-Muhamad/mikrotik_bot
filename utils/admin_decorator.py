from functools import wraps
import logging
import threading
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

ADMIN_ONLY_MSG = "❌ هذا البوت مخصص للأدمن فقط."

ROLE_LEVELS = {"admin": 30, "operator": 20, "viewer": 10}
ROLE_LABELS = {
    "admin": "👑 مالك/أدمن",
    "operator": "🛠️ مشغّل",
    "viewer": "👁️ مشاهد",
}
INSUFFICIENT_ROLE_MSG = "⛔ صلاحيتك غير كافية لتنفيذ هذا الأمر."

RATE_LIMIT_WINDOW = 1.0
_RATE_LIMIT_MAX_AGE = 3600
_RATE_LIMIT_CLEANUP_INTERVAL = 300.0
_rate_limit_data: dict[int, float] = {}
_last_cleanup: float = 0.0
_rate_limit_lock = threading.Lock()


def reset_rate_limit(user_id: int):
    """Reset rate limit for a user — call after successful router connection."""
    with _rate_limit_lock:
        _rate_limit_data.pop(user_id, None)


def _check_rate_limit(user_id: int) -> bool:
    global _last_cleanup
    now = time.monotonic()

    with _rate_limit_lock:
        if now - _last_cleanup > _RATE_LIMIT_CLEANUP_INTERVAL:
            stale = [uid for uid, ts in list(_rate_limit_data.items()) if now - ts > _RATE_LIMIT_MAX_AGE]
            for uid in stale:
                del _rate_limit_data[uid]
            _last_cleanup = now

        last = _rate_limit_data.get(user_id, 0.0)
        if now - last < RATE_LIMIT_WINDOW:
            return False
        _rate_limit_data[user_id] = now
        return True


def _is_group_chat(update: Update) -> bool:
    chat = update.effective_chat
    if chat:
        chat_type = getattr(chat, 'type', None)
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
            chat_id = update.effective_chat.id if update.effective_chat else "unknown"
            logger.warning(
                f"UNAUTHORIZED ACCESS: user_id={user_id}, "
                f"function={func.__name__}, "
                f"chat_id={chat_id}"
            )
            await _send_reply(update, ADMIN_ONLY_MSG)
            return

        if not _check_rate_limit(user_id):
            if update.callback_query:
                try:
                    await update.callback_query.answer(text="⏳", show_alert=False)
                except Exception:
                    pass
            return

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

            if user_id not in ADMIN_IDS:
                logger.warning(
                    f"UNAUTHORIZED ACCESS: user_id={user_id}, "
                    f"function={func.__name__}"
                )
                await _send_reply(update, ADMIN_ONLY_MSG)
                return

            from database.models import get_admin_role

            role = get_admin_role(user_id) or "admin"
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
