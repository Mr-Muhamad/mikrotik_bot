"""Safe callback query helpers.

Provides wrappers that handle common Telegram callback query errors gracefully.
"""

import logging
import time

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


async def safe_answer_callback(query, text: str | None = None, show_alert: bool = False):
    """Safely answer a callback query, ignoring 'Query is too old' errors.

    This error occurs when the bot takes too long (>30s) to respond
    to a callback query. It's non-critical and can be safely ignored.

    Args:
        query: The callback query object.
        text: Optional text to show in notification.
        show_alert: Whether to show as alert popup.
    """
    try:
        await query.answer(text=text, show_alert=show_alert)
    except Exception as e:
        error_msg = str(e)
        if "Query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.debug(f"Callback answer timeout (non-critical): {getattr(query, 'data', 'unknown')}")
        else:
            logger.warning(f"Callback answer failed: {e}")
