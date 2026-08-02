import logging
from collections.abc import Callable
from dataclasses import dataclass

import telegram.error
from librouteros.exceptions import LibRouterosError
from telegram import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from core.metrics import record_error
from utils.chat_cleaner import track_msg
from utils.formatters import sanitize_text as _sanitize_error_text
from utils.logging_setup import (
    COMPONENT_HANDLER,
    COMPONENT_TELEGRAM,
    get_request_id,
    get_trace_id,
)
from utils.tg_helpers import get_query_chat_id, get_query_message

logger = logging.getLogger(__name__)

CATEGORY_CONNECTION = "connection"
CATEGORY_AUTH = "auth"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_NOT_FOUND = "not_found"
CATEGORY_STORAGE = "storage"
CATEGORY_GENERAL = "general"

ERROR_MESSAGES: dict[str, str] = {
    CATEGORY_CONNECTION: "❌ تعذر الاتصال بالروتر. تأكد من أن الجهاز قيد التشغيل ومتصل بالشبكة.",
    CATEGORY_AUTH: "❌ فشل تسجيل الدخول إلى الروتر. تحقق من اسم المستخدم وكلمة المرور.",
    CATEGORY_TIMEOUT: "⏱️ لم يستجب الروتر خلال المهلة المحددة. حاول مرة أخرى لاحقاً.",
    CATEGORY_NOT_FOUND: "🔍 الروتر غير موجود. تأكد من اختيار روتر صحيح أو استخدم /start لإعادة الاكتشاف.",
    CATEGORY_STORAGE: "💾 مساحة التخزين على سيرفر البوت غير كافية أو يتعذر كتابة الملفات المحلية.",
    CATEGORY_GENERAL: "❌ حدث خطأ غير متوقع. حاول مرة أخرى أو استخدم /start.",
}

# Public alias — external modules should import this instead of the private form.
sanitize_error_text = _sanitize_error_text

# رسائل خطأ Telegram الحميدة: تحدث أثناء الاستخدام الطبيعي لتعديل الرسائل
# (المحتوى لم يتغير أو الرسالة محذوفة) ولا تستدعي إشعاراً للمستخدم أو سجلاً على مستوى الخطأ.
_BENIGN_TELEGRAM_MESSAGES = (
    "Message is not modified",
    "Message to edit not found",
    "exactly the same content",
)


def is_benign_telegram_error(error: Exception) -> bool:
    """تحديد أخطاء Telegram الحميدة التي لا تستدعي رسالة خطأ للمستخدم."""
    if isinstance(error, BadRequest):
        msg = str(error)
        return any(s in msg for s in _BENIGN_TELEGRAM_MESSAGES)
    return False


def _classify_librouteros(error: LibRouterosError) -> str:
    msg = str(error).lower()
    if "timeout" in msg:
        return CATEGORY_TIMEOUT
    if any(kw in msg for kw in ("refused", "closed", "reset", "unreachable")):
        return CATEGORY_CONNECTION
    if any(kw in msg for kw in ("auth", "password", "login", "credentials", "unauthorized")):
        return CATEGORY_AUTH
    if any(kw in msg for kw in ("not found", "no such", "invalid argument")):
        return CATEGORY_NOT_FOUND
    return CATEGORY_GENERAL


def _classify_os_error(error: TimeoutError | ConnectionError | OSError) -> str:
    msg = str(error).lower()
    if "timeout" in msg or "timed out" in msg:
        return CATEGORY_TIMEOUT
    if any(kw in msg for kw in ("space", "disk full", "nospc", "permission denied")):
        return CATEGORY_STORAGE
    return CATEGORY_CONNECTION


_ERROR_CLASSIFIERS: list[tuple[type[Exception], Callable[..., str]]] = [
    (LibRouterosError, _classify_librouteros),
    (OSError, _classify_os_error),
]


def classify_error(error: Exception) -> str:
    for exc_type, classifier in _ERROR_CLASSIFIERS:
        if isinstance(error, exc_type):
            return classifier(error)

    if isinstance(error, ValueError) and "not found" in str(error).lower():
        return CATEGORY_NOT_FOUND

    try:
        import httpx

        if isinstance(error, httpx.TimeoutException):
            return CATEGORY_TIMEOUT
        if isinstance(error, httpx.ConnectError):
            return CATEGORY_CONNECTION
    except ImportError:
        pass  # guard: optional dependency — httpx is not installed

    return CATEGORY_GENERAL


@dataclass
class ErrorContext:
    """Structured context for error logging and notifications."""

    router_key: str | None = None
    command: str | None = None
    user_id: int | None = None
    chat_id: int | None = None
    request_id: str | None = None
    trace_id: str | None = None
    attempt: int | None = None
    duration_ms: float | None = None


def log_error(
    error: Exception,
    component: str = COMPONENT_HANDLER,
    context: ErrorContext | None = None,
) -> None:
    """Log an error with structured fields including error_category.

    Uses the existing request_id, component, and trace_id ContextVars
    for correlation, and additionally attaches any fields from the
    provided ErrorContext dataclass.
    """
    category = classify_error(error)
    extra: dict[str, object] = {
        "component": component,
        "request_id": get_request_id(),
        "trace_id": (context.trace_id if context else get_trace_id()),
        "error_category": category,
    }
    if context:
        if context.router_key:
            extra["router_key"] = context.router_key
        if context.command:
            extra["command"] = context.command
        if context.user_id is not None:
            extra["user_id"] = context.user_id
        if context.chat_id is not None:
            extra["chat_id"] = context.chat_id
        if context.duration_ms is not None:
            extra["duration_ms"] = context.duration_ms
        if context.attempt is not None:
            extra["attempt"] = context.attempt

    logger.error(
        "%s: %s | type=%s",
        category, _sanitize_error_text(str(error)[:200]), type(error).__name__,
        extra=extra,
        exc_info=True,
    )


def format_error_message(error: Exception, router_key: str | None = None) -> str:
    from utils.logging_setup import get_request_id

    category = classify_error(error)
    msg = ERROR_MESSAGES[category]
    if category in (CATEGORY_GENERAL, CATEGORY_STORAGE):
        # تنظيف النص من أي أسرار قبل عرضه للمستخدم
        short = _sanitize_error_text(str(error)[:200])
        if short:
            msg += f"\n📋 {short}"
    # إضافة معرف الروتر إذا كان متاحاً
    if router_key:
        msg += f"\n🆔 {router_key}"

    req_id = get_request_id()
    if req_id and req_id != "-":
        msg += f"\n🔍 مرجع البلاغ: <code>#{req_id}</code>"
    return msg


async def _dispatch_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None,
    target_id: int,
    error_label: str,
) -> None:
    try:
        query = update.callback_query if update else None
        query_msg = get_query_message(query)
        if query is not None and query_msg is not None:
            query_chat_id = get_query_chat_id(query)
            if query_chat_id is not None and query_chat_id != target_id:
                msg = await context.bot.send_message(
                    chat_id=target_id, text=text, reply_markup=reply_markup,
                )
            else:
                # edit_message_text only accepts InlineKeyboardMarkup | None
                msg = await query.edit_message_text(
                    text=text,
                    reply_markup=(
                        reply_markup if isinstance(reply_markup, InlineKeyboardMarkup) else None
                    ),
                )
        elif update and update.effective_message:
            msg = await update.effective_message.reply_text(text=text, reply_markup=reply_markup)
        else:
            msg = await context.bot.send_message(
                chat_id=target_id, text=text, reply_markup=reply_markup
            )
        if isinstance(msg, Message):
            track_msg(context, target_id, msg.message_id)
    except telegram.error.TelegramError as send_err:
        if is_benign_telegram_error(send_err):
            logger.debug(
                "Benign Telegram error (ignored in _dispatch_message): %s | type=%s",
                _sanitize_error_text(str(send_err)), type(send_err).__name__,
                extra={"component": COMPONENT_TELEGRAM},
            )
            return
        logger.error(
            "%s: %s",
            error_label, _sanitize_error_text(str(send_err)),
            exc_info=True,
            extra={"component": COMPONENT_TELEGRAM},
        )


async def send_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    router_key: str | None = None,
    log_extra: str = "",
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
    chat_id: int | None = None,
    error_context: ErrorContext | None = None,
) -> None:
    from utils.logging_setup import get_trace_id

    error_text = _sanitize_error_text(str(error))
    # الأخطاء الحميدة (مثل "Message is not modified") شائعة أثناء تعديل الرسائل
    # ولا تستدعي تنبيهاً للمستخدم أو سجلاً على مستوى الخطأ.
    if is_benign_telegram_error(error):
        logger.debug(
            "Benign Telegram error (ignored): %s | type=%s",
            error_text, type(error).__name__,
            extra={"component": COMPONENT_HANDLER},
        )
        return
    effective_router_key = router_key or get_router_key_from_context(context)
    category = classify_error(error)
    text = format_error_message(error, effective_router_key)
    log_msg = f"{log_extra}: {error_text}" if log_extra else error_text
    extra: dict[str, object] = {
        "component": COMPONENT_HANDLER,
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "error_category": category,
        "router_key": effective_router_key,
    }
    if error_context:
        if error_context.command:
            extra["command"] = error_context.command
        if error_context.user_id is not None:
            extra["user_id"] = error_context.user_id
        if error_context.chat_id is not None:
            extra["chat_id"] = error_context.chat_id
        if error_context.duration_ms is not None:
            extra["duration_ms"] = error_context.duration_ms
    logger.error(
        "ERROR [%s]: %s",
        category, log_msg,
        extra=extra,
        exc_info=True,
    )
    # Track error in metrics
    record_error(category, COMPONENT_HANDLER)
    # Critical error notifications to Telegram admins for connection/auth/storage issues
    if category in (CATEGORY_CONNECTION, CATEGORY_AUTH, CATEGORY_STORAGE):
        await _notify_critical_admins(update, context, error, category, effective_router_key, text)
    target_id = chat_id or _get_chat_id(update)
    if target_id is None:
        return
    await _dispatch_message(
        update, context, text, reply_markup, target_id, "Failed to send error message"
    )


async def send_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
    chat_id: int | None = None,
) -> None:
    target_id = chat_id or _get_chat_id(update)
    if target_id is None:
        return
    await _dispatch_message(
        update, context, text, reply_markup, target_id, "Failed to send message"
    )


def _get_chat_id(update: Update | None) -> int | None:
    if update is None:
        return None
    chat_id = get_query_chat_id(update.callback_query)
    if chat_id is not None:
        return chat_id
    if update.effective_message:
        return update.effective_message.chat_id
    if update.effective_chat:
        return update.effective_chat.id
    return None


def get_router_key_from_context(
    context: ContextTypes.DEFAULT_TYPE | None,
    default: str | None = None,
) -> str | None:
    user_data = getattr(context, "user_data", None) if context else None
    if not isinstance(user_data, dict):
        return default
    key = user_data.get("selected_router") or user_data.get("router_key")
    return key if isinstance(key, str) and key else default


async def _notify_critical_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    category: str,
    router_key: str | None,
    user_message: str,
) -> None:
    """Notify Telegram admins about critical errors (connection/auth/storage)."""
    from config import ADMIN_IDS

    req_id = get_request_id()
    router_info = f" | router={router_key}" if router_key else ""
    text = "\U0001f6a8 <b>Critical Bot Error</b>\n\n"
    text += f"Category: <code>{category}</code>{router_info}\n"
    text += f"Ref: #{req_id}\n"
    text += f"Error: {_sanitize_error_text(str(error)[:300])}"

    for admin_id in ADMIN_IDS:
        try:
            await send_text(
                update, context, text, chat_id=admin_id
            )
        except Exception:  # noqa: BLE001 - catch-all: notification failures must not break main error handling
            logger.exception(
                "Failed to notify admin %d about critical error %s", admin_id, category
            )
