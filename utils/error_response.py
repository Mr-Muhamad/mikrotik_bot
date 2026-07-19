import logging
import re
from typing import Any

from librouteros.exceptions import LibRouterosError
from telegram import Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from utils.chat_cleaner import _track_msg
from bot.handlers.handler_utils import get_query_message, get_query_chat_id

logger = logging.getLogger(__name__)

CATEGORY_CONNECTION = "connection"
CATEGORY_AUTH = "auth"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_NOT_FOUND = "not_found"
CATEGORY_GENERAL = "general"

ERROR_MESSAGES: dict[str, str] = {
    CATEGORY_CONNECTION: "❌ تعذر الاتصال بالروتر. تأكد من أن الجهاز قيد التشغيل ومتصل بالشبكة.",
    CATEGORY_AUTH: "❌ فشل تسجيل الدخول إلى الروتر. تحقق من اسم المستخدم وكلمة المرور.",
    CATEGORY_TIMEOUT: "⏱️ لم يستجب الروتر خلال المهلة المحددة. حاول مرة أخرى لاحقاً.",
    CATEGORY_NOT_FOUND: "🔍 الروتر غير موجود. تأكد من اختيار روتر صحيح أو استخدم /start لإعادة الاكتشاف.",
    CATEGORY_GENERAL: "❌ حدث خطأ غير متوقع. حاول مرة أخرى أو استخدم /start.",
}

# كلمات تدل على أسرار محتملة في رسائل الخطأ
_SECRET_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "private",
    "api[_-]?key",
)

# أنماط لإخفاء المعرّفات الحساسة (IP قد يكون حساساً، لكن نتركه لأن المستخدمين يحتاجونه)
_SECRET_PATTERNS = [
    # key=value أو key: value — 2 مجموعات: (prefix) + (value to replace)
    # يخفي فقط القيم التي تزيد عن 5 أحرف لتجنب إخفاء كلمات قصيرة مثل "admin"
    re.compile(
        r"(?i)(" + "|".join(_SECRET_KEYWORDS) + r")\s*[=:]\s*(\S{6,})",
    ),
    # Authorization: Bearer xxx
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)"),
    # Basic Auth header
    re.compile(r"(?i)(basic\s+)([A-Za-z0-9+/=]+)"),
]

_SANITIZED_PLACEHOLDER = "[إخفاء]"


def _sanitize_error_text(raw: str) -> str:
    """إخفاء أي أسرار محتملة في نص الخطأ قبل عرضه للمستخدم.

    الأمان أولاً: عند الشك، نُخفي. السجلات الكاملة تبقى في logger.
    """
    if not raw:
        return raw
    sanitized = raw
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(rf"\1{_SANITIZED_PLACEHOLDER}", sanitized)
    return sanitized


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


def classify_error(error: Exception) -> str:
    if isinstance(error, LibRouterosError):
        msg = str(error).lower()
        if "timeout" in msg:
            return CATEGORY_TIMEOUT
        if any(kw in msg for kw in ("refused", "closed", "reset", "unreachable")):
            return CATEGORY_CONNECTION
        if any(
            kw in msg
            for kw in ("auth", "password", "login", "credentials", "unauthorized")
        ):
            return CATEGORY_AUTH
        if any(kw in msg for kw in ("not found", "no such", "invalid argument")):
            return CATEGORY_NOT_FOUND
        return CATEGORY_GENERAL
    if isinstance(error, (ConnectionError, OSError)):
        msg = str(error).lower()
        if "timeout" in msg:
            return CATEGORY_TIMEOUT
        return CATEGORY_CONNECTION
    if isinstance(error, ValueError):
        msg = str(error).lower()
        if "not found" in msg:
            return CATEGORY_NOT_FOUND
    return CATEGORY_GENERAL


def format_error_message(error: Exception, router_key: str | None = None) -> str:
    category = classify_error(error)
    msg = ERROR_MESSAGES[category]
    if category == CATEGORY_GENERAL:
        # تنظيف النص من أي أسرار قبل عرضه للمستخدم
        short = _sanitize_error_text(str(error)[:200])
        if short:
            msg += f"\n📋 {short}"
    # إضافة معرف الروتر إذا كان متاحاً
    if router_key:
        msg += f"\n🆔 {router_key}"
    return msg


async def _dispatch_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: Any,
    target_id: int,
    error_label: str,
) -> None:
    try:
        query = update.callback_query if update else None
        query_msg = get_query_message(query)
        if query is not None and query_msg is not None:
            msg = await query.edit_message_text(text=text, reply_markup=reply_markup)
        elif update and update.effective_message:
            msg = await update.effective_message.reply_text(
                text=text, reply_markup=reply_markup
            )
        else:
            msg = await context.bot.send_message(
                chat_id=target_id, text=text, reply_markup=reply_markup
            )
        if msg is not None and isinstance(msg, Message):
            _track_msg(context, target_id, msg.message_id)
    except Exception as send_err:
        if is_benign_telegram_error(send_err):
            logger.debug(
                f"Benign Telegram error (ignored in _dispatch_message): "
                f"{_sanitize_error_text(str(send_err))} | type={type(send_err).__name__}"
            )
            return
        logger.error(f"{error_label}: {_sanitize_error_text(str(send_err))}")


async def send_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    router_key: str | None = None,
    log_extra: str = "",
    reply_markup: Any = None,
    chat_id: int | None = None,
) -> None:
    error_text = _sanitize_error_text(str(error))
    # الأخطاء الحميدة (مثل "Message is not modified") شائعة أثناء تعديل الرسائل
    # ولا تستدعي تنبيهاً للمستخدم أو سجلاً على مستوى الخطأ.
    if is_benign_telegram_error(error):
        logger.debug(
            f"Benign Telegram error (ignored): {error_text} | type={type(error).__name__}"
        )
        return
    effective_router_key = router_key or get_router_key_from_context(context)
    text = format_error_message(error, effective_router_key)
    log_msg = f"{log_extra}: {error_text}" if log_extra else error_text
    logger.error(f"{log_msg} | type={type(error).__name__}")
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
    reply_markup: Any = None,
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
