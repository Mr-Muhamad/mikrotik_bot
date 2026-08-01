"""Safe callback query helpers.

Provides wrappers that handle common Telegram callback query errors gracefully.
"""

import logging
import time

from telegram import CallbackQuery

from utils.formatters import sanitize_log_data
from utils.logging_setup import COMPONENT_TELEGRAM
from utils.request_id import get_request_id, get_trace_id

logger = logging.getLogger(__name__)

_CALLBACK_DEDUP: dict[str, float] = {}
_DEDUP_WINDOW = 1.0
_DEDUP_MAX_AGE = 60.0
_DEDUP_CLEANUP_INTERVAL = 30.0
_last_cleanup: float = 0.0


def is_duplicate_callback(callback_data: str | None, user_id: int | None = None) -> bool:
    if not callback_data:
        return False
    global _last_cleanup
    now = time.monotonic()
    key = f"{user_id}:{callback_data}" if user_id else callback_data
    last = _CALLBACK_DEDUP.get(key, 0.0)
    if now - last < _DEDUP_WINDOW:
        return True
    _CALLBACK_DEDUP[key] = now

    # Periodic cleanup to prevent unbounded growth
    if now - _last_cleanup > _DEDUP_CLEANUP_INTERVAL:
        old_keys = [k for k, t in list(_CALLBACK_DEDUP.items()) if now - t > _DEDUP_MAX_AGE]
        for k in old_keys:
            _CALLBACK_DEDUP.pop(k, None)
        _last_cleanup = now

    return False


async def safe_answer_callback(
    query: CallbackQuery | None, text: str | None = None, show_alert: bool = False
) -> None:
    """Safely answer a callback query, ignoring 'Query is too old' errors.

    This error occurs when the bot takes too long (>30s) to respond
    to a callback query. It's non-critical and can be safely ignored.

    Args:
        query: The callback query object, or None to skip answering.
        text: Optional text to show in notification.
        show_alert: Whether to show as alert popup.
    """
    if query is None:
        return
    start = time.monotonic()
    try:
        await query.answer(text=text, show_alert=show_alert)
    except Exception as e:  # noqa: BLE001 - catch-all: log unexpected error before returning result
        duration_ms = (time.monotonic() - start) * 1000
        error_msg = str(e)
        if "Query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.debug(
                "Callback answer timeout (non-critical): %s",
                getattr(query, "data", "unknown"),
                extra={
                    "component": COMPONENT_TELEGRAM,
                    "request_id": get_request_id(),
                    "trace_id": get_trace_id(),
                    "duration_ms": duration_ms,
                    "success": False,
                },
                exc_info=True,
            )
        else:
            logger.warning(
                "Callback answer failed (error type: %s): %s",
                type(e).__name__, sanitize_log_data(str(e)),
                extra={
                    "component": COMPONENT_TELEGRAM,
                    "request_id": get_request_id(),
                    "trace_id": get_trace_id(),
                    "duration_ms": duration_ms,
                    "success": False,
                    "error_category": _classify_callback_error(e),
                },
                exc_info=True,
            )
    else:
        duration_ms = (time.monotonic() - start) * 1000
        logger.debug(
            "Callback answered: %s",
            getattr(query, "data", "unknown"),
            extra={
                "component": COMPONENT_TELEGRAM,
                "request_id": get_request_id(),
                "trace_id": get_trace_id(),
                "duration_ms": duration_ms,
                "success": True,
            },
        )


def is_latest_message(query: CallbackQuery | None, user_data: dict[str, object] | None) -> bool:
    """Check if the callback query originates from the active/latest message.

    Args:
        query: The incoming callback query.
        user_data: The context.user_data dict containing 'last_msg'.

    Returns:
        True if query is from the latest message or no last_msg tracked, False otherwise.
    """
    if query is None or query.message is None or user_data is None:
        return True
    last_msg_id = user_data.get("last_msg")
    if last_msg_id is not None:
        return query.message.message_id == int(str(last_msg_id))
    return True


def _classify_callback_error(error: Exception) -> str:
    """Classify a callback answer error for structured logging."""
    msg = str(error).lower()
    if "query is too old" in msg or "query id is invalid" in msg:
        return "stale_callback"
    if "bot was blocked" in msg or "user blocked" in msg:
        return "user_blocked"
    if "timeout" in msg:
        return "timeout"
    return "telegram_error"
