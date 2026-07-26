import asyncio
import logging
from collections.abc import Generator, Sequence
from datetime import UTC
from typing import TypedDict, cast

from telegram import CallbackQuery, InlineKeyboardMarkup, Message, Update
from telegram.ext import CallbackContext, ExtBot, JobQueue

from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

# Type alias for the bot context used across this module
_CleanerContext = CallbackContext[ExtBot[None], RouterOSRow, RouterOSRow, RouterOSRow]
_Update = Update
_CallbackQuery = CallbackQuery

DELETE_DELAY = 120  # دقيقتين — وقت مناسب للمستخدم للقراءة والتفاعل
MAX_TRACKED_MSGS = 200
MAX_MESSAGE_LENGTH = 4090
MESSAGE_TRUNCATION_SUFFIX = "\n\n... (تم اقتطاع الرسالة لطولها)"

# عمر أقصى لتتبع الرسائل في الذاكرة (ساعتين) قبل تنظيفها
CHAT_MSGS_TTL_SECONDS = 2 * 3600

# Max messages per single delete_messages call (Bot API limit is 100)
DELETE_MESSAGES_CHUNK = 100


# إحصائيات الأداء (للمراقبة)
class _Stats(TypedDict):
    messages_tracked: int
    messages_deleted: int
    cleanup_runs: int


_stats: _Stats = {
    "messages_tracked": 0,
    "messages_deleted": 0,
    "cleanup_runs": 0,
}

# أنواع الشاتات التي يُتخطّى فيها التنظيف التلقائي بالكامل.
#   - channel: محمية، لأن البوت قد ينشر بصفتها ولا يُراد عادةً حذف منشوراته.
#   - group/supergroup: يملك البوت حذف رسائله الصادرة فيها، لذا تُنظَّف عبر /clean.
# ملاحظة: رسائل المستخدمين لا تُحذف إلا في المحادثة الخاصة (معالَجة في _send_replacing_last).
_PROTECTED_CHAT_TYPES = {"channel"}


# رسائل أخطاء Telegram الحميدة عند تعديل الرسائل
_BENIGN_EDIT_ERRORS = (
    "Message is not modified",
    "Message to edit not found",
    "exactly the same",
)


def _is_benign_edit_error(err: Exception) -> bool:
    """تحديد أخطاء تعديل الرسائل الحميدة التي يجب تجاهلها بصمت."""
    return any(s in str(err) for s in _BENIGN_EDIT_ERRORS)


def _track_msg(
    context: _CleanerContext,
    chat_id: int,
    message_id: int,
    chat_type: str | None = None,
) -> None:
    """تتبع رسالة للتنظيف التلقائي عبر قاعدة البيانات.

    لا يُتتبَّع إلا رسائل البوت الصادرة. تُتخطّى القنوات (channel) فقط؛ أمّا
    المجموعات فيُسمح فيها للبوت بحذف رسائله، لذا تُتتبَّع وتُنظَّف عبر /clean.
    """
    # إذا عرفنا نوع الشات مسبقاً، نتخطى التتبع في المجموعات
    if chat_type and chat_type in _PROTECTED_CHAT_TYPES:
        return

    from database.models import add_tracked_message

    add_tracked_message(chat_id, message_id)
    _stats["messages_tracked"] += 1


track_msg = _track_msg


async def clean_chat_messages(
    context: _CleanerContext,
    chat_id: int,
    chat_type: str | None = None,
) -> None:
    """Delete all tracked (bot) messages for a chat and remove them from tracking.

    تُتخطّى القنوات (channel) بالكامل. في المجموعات/السوبر-جروب يُسمح للبوت بحذف
    رسائله الصادرة فيُنظَّف ما تتبَّع منه. رسائل المستخدمين لا تُمسّ هنا.
    """
    if chat_type and chat_type in _PROTECTED_CHAT_TYPES:
        return
    cached_type: str | None = cast(str | None, context.bot_data.get(f"_chat_type_{chat_id}"))
    if cached_type and cached_type in _PROTECTED_CHAT_TYPES:
        return

    from database.models import get_tracked_messages, remove_tracked_messages

    msgs_ids: list[int] | None = get_tracked_messages(chat_id)
    if not msgs_ids:
        return

    _stats["cleanup_runs"] += 1
    deleted_count = 0
    for chunk in _chunks(msgs_ids, DELETE_MESSAGES_CHUNK):
        deleted_count += await _delete_message_ids(context, chat_id, chunk)
        # Always remove from DB even if Telegram failed (e.g. older than 48h or already deleted)
        remove_tracked_messages(chat_id, chunk)

    _stats["messages_deleted"] += deleted_count


def _chunks(items: Sequence[int], size: int) -> Generator[list[int], None, None]:
    """Yield successive chunks of ``items`` bounded by ``size`` elements."""
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


async def _delete_message_ids(
    context: _CleanerContext,
    chat_id: int,
    message_ids: list[int],
) -> int:
    """Delete a set of message ids efficiently with resilient per-message fallback.

    Uses the batched ``delete_messages`` API (available in PTB 22.7) when there is
    more than one message. If the batch call raises or only partially succeeds
    (e.g. a message older than 48h), it retries each message individually so a
    single stale message does not block the rest.
    """
    if not message_ids:
        return 0

    if len(message_ids) == 1:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_ids[0])
            return 1
        except Exception as e:
            logger.debug(f"Failed to delete message {message_ids[0]} in chat {chat_id}: {e}")
            return 0

    try:
        result = await context.bot.delete_messages(chat_id=chat_id, message_ids=message_ids)
        if result is True:
            return len(message_ids)
    except Exception as e:
        logger.debug(f"Batched delete failed for chat {chat_id}: {e}")

    deleted = 0
    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted += 1
        except Exception as e:
            logger.debug(f"Failed to delete message {mid} in chat {chat_id}: {e}")
        # Throttle to prevent FloodWait when deleting many individual messages
        await asyncio.sleep(0.05)
    return deleted


def _delete_job_name(chat_id: int, message_id: int) -> str:
    return f"del_{chat_id}_{message_id}"


async def schedule_delete(
    context: _CleanerContext,
    chat_id: int,
    message_id: int | None,
    delay: int = DELETE_DELAY,
) -> None:
    """Schedule automatic deletion of a message after a delay in seconds."""
    if not message_id:
        return
    job_name = _delete_job_name(chat_id, message_id)
    job_queue: JobQueue = context.job_queue  # type: ignore[assignment]
    existing = list(job_queue.get_jobs_by_name(job_name))
    for j in existing:
        j.schedule_removal()
    job_queue.run_once(
        _delete_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=job_name,
    )


async def _delete_job(context: _CleanerContext) -> None:
    data = cast(dict[str, object], context.job.data)  # type: ignore[union-attr]
    try:
        await context.bot.delete_message(
            chat_id=str(data["chat_id"]),
            message_id=int(str(data["message_id"])),
        )
        _stats["messages_deleted"] += 1
    except Exception as e:
        logger.debug(f"Delete failed: {e}")


async def delete_now(context: _CleanerContext, chat_id: int, message_id: int) -> None:
    """Immediately delete a specific message, ignoring errors silently."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        _stats["messages_deleted"] += 1
    except Exception as e:
        logger.debug(f"delete_now failed: {e}")


def track_message(context: _CleanerContext, chat_id: int, message_id: int) -> None:
    """Register an already-sent message for future cleanup via /clean."""
    _track_msg(context, chat_id, message_id)


async def clean_command(update: _Update, context: _CleanerContext) -> None:
    """Delete the user's command message that triggered this handler."""
    if update.message:
        await delete_now(context, update.effective_chat.id, update.message.message_id)


async def send_and_track(
    context: _CleanerContext,
    chat_id: int,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> Message:
    """Send a message and track it for cleanup — unified helper."""
    msg = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=parse_mode
    )
    _track_msg(context, chat_id, msg.message_id)
    return msg


async def send_loading(
    update: _Update,
    context: _CleanerContext,
    text: str = "⏳ جاري العمل...",
) -> Message:
    """Send a loading indicator message and track it for future cleanup."""
    chat_id = update.effective_chat.id
    # الرسالة عابرة (مؤشر تحميل) — لا نطلق إشعاراً للمستخدم
    msg = await context.bot.send_message(chat_id=chat_id, text=text, disable_notification=True)
    _track_msg(context, chat_id, msg.message_id)
    return msg


def _truncate(text: str) -> str:
    if len(text) > MAX_MESSAGE_LENGTH:
        text = (
            text[: MAX_MESSAGE_LENGTH - len(MESSAGE_TRUNCATION_SUFFIX)] + MESSAGE_TRUNCATION_SUFFIX
        )
    return text


async def safe_edit_or_send(
    query: CallbackQuery | None,
    context: _CleanerContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Edit the callback message in place; fall back to a new message if edit fails.

    Handles the case where the original message was deleted (e.g., by /clean or
    a previous send_step) — instead of a silent no-op, a fresh message is sent
    so the user always gets a visible response.
    """
    if query is None:
        return None
    text = _truncate(text)
    message = query.message
    if message is None:
        return None
    chat_id = cast(int | None, getattr(message, "chat_id", None))
    if not chat_id:
        return None
    try:
        edited: Message | bool = await query.edit_message_text(
            text=text, reply_markup=keyboard, parse_mode="HTML"
        )
        if isinstance(edited, Message):
            _track_msg(context, chat_id, edited.message_id)
            context.user_data["last_msg"] = edited.message_id
            return edited
        return None
    except Exception as e:
        str(e)
        if _is_benign_edit_error(e):
            prev = context.user_data.pop("last_msg", None)
            if prev is not None:
                await delete_now(context, chat_id, int(prev))
            msg = await context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
            )
            _track_msg(context, chat_id, msg.message_id)
            context.user_data["last_msg"] = msg.message_id
            return msg
        raise


async def edit_clean(
    query: CallbackQuery | None,
    context: _CleanerContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Edit a callback query message with new text and track the edit for cleanup."""
    if query is None:
        return None
    text = _truncate(text)
    message = query.message
    chat_id = 0
    if message is not None:
        chat_id = cast(int, getattr(message, "chat_id", 0))
        if chat_id == 0:
            return None
    try:
        edited: Message | bool = await query.edit_message_text(
            text=text, reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception as e:
        if _is_benign_edit_error(e):
            # المحتوى لم يتغير أو الرسالة محذوفة — حالة حميدة، نتجاهلها بصمت
            logger.debug(f"edit_clean benign skip: {e}")
            return None
        raise
    if isinstance(edited, Message) and message is not None:
        _track_msg(context, chat_id, edited.message_id)
        context.user_data["last_msg"] = edited.message_id
    return edited if isinstance(edited, Message) else None


async def safe_edit_plain(
    query: CallbackQuery | None,
    context: _CleanerContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """عدّل رسالة الاستدعاء مع تجاهل أخطاء التعديل الحميدة.

    يُبقي على parse_mode الافتراضي (بدون HTML) المستخدم في الاستدعاءات المباشرة
    لـ ``query.edit_message_text``، ويتجاهل أخطاء مثل "Message is not modified"
    دون إنهاء تدفق المحادثة.
    """
    if query is None:
        return None
    message = query.message
    chat_id = 0
    if message is not None:
        chat_id = cast(int, getattr(message, "chat_id", 0))
        if chat_id == 0:
            return None
    try:
        edited: Message | bool = await query.edit_message_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        if _is_benign_edit_error(e):
            logger.debug(f"safe_edit_plain benign skip: {e}")
            return None
        raise
    if isinstance(edited, Message) and message is not None:
        _track_msg(context, chat_id, edited.message_id)
        context.user_data["last_msg"] = edited.message_id
    return edited if isinstance(edited, Message) else None


async def _send_replacing_last(
    update: _Update,
    context: _CleanerContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None,
) -> Message | None:
    """Delete the triggering message and the previous step, then send a fresh message.

    الرسالة المُطلِقة (رسالة المستخدم) تُحذف في المحادثة الخاصة فقط، لأن بوت
    تليجرام لا يملك صلاحية حذف رسائل المستخدمين في المجموعات/القنوات إلا إن كان
    أدمناً. رسالة البوت السابقة (last_msg) تُحذف في كل الأنواع لأن البوت يحذف
    رسائله الصادرة أينما كانت.
    """
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type if update.effective_chat else None
    if update.message and chat_type == "private":
        await delete_now(context, chat_id, update.message.message_id)
    prev = context.user_data.pop("last_msg", None)
    if prev is not None:
        await delete_now(context, chat_id, int(prev))
    msg = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
    )
    _track_msg(context, chat_id, msg.message_id)
    return msg


async def send_step(
    update: _Update,
    context: _CleanerContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Send a new step message while cleaning up the previous step message."""
    text = _truncate(text)
    msg = await _send_replacing_last(update, context, text, keyboard)
    if msg is not None:
        context.user_data["last_msg"] = msg.message_id
    return msg


async def reply_final(
    update: _Update,
    context: _CleanerContext,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Send a final reply message while cleaning up the previous step message."""
    text = _truncate(text)
    return await _send_replacing_last(update, context, text, keyboard)


async def run_background_cleanup(context: _CleanerContext) -> None:
    """Background task to remove old tracked messages from the database.

    Messages older than 48 hours cannot be deleted from Telegram anyway,
    so we just purge them from the database to prevent unbounded growth.
    """
    from datetime import datetime, timedelta

    from database.models import UTC_TIMESTAMP_FORMAT, cleanup_health_history, delete_stale_records

    cutoff = datetime.now(UTC) - timedelta(hours=48)
    cutoff_str = cutoff.strftime(UTC_TIMESTAMP_FORMAT)
    delete_stale_records(cutoff_str)

    # Also cleanup old router health logs
    cleaned_health = cleanup_health_history(days=7)
    if cleaned_health > 0:
        logger.debug(f"Cleaned {cleaned_health} old router health records.")


def get_cleanup_stats() -> _Stats:
    """إرجاع إحصائيات الأداء للمراقبة."""
    return _stats.copy()
