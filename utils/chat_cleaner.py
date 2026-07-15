import logging
import time

logger = logging.getLogger(__name__)

DELETE_DELAY = 120  # دقيقتين — وقت مناسب للمستخدم للقراءة والتفاعل
MAX_TRACKED_MSGS = 200
MAX_MESSAGE_LENGTH = 4090
MESSAGE_TRUNCATION_SUFFIX = "\n\n... (تم اقتطاع الرسالة لطولها)"

# عمر أقصى لتتبع الرسائل في الذاكرة (ساعتين) قبل تنظيفها
CHAT_MSGS_TTL_SECONDS = 2 * 3600

# Max messages per single delete_messages call (Bot API limit is 100)
DELETE_MESSAGES_CHUNK = 100

# إحصائيات الأداء (للمراقبة)
_stats = {
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



def _track_msg(context, chat_id, message_id, chat_type=None):
    """تتبع رسالة للتنظيف التلقائي مع TTL.

    لا يُتتبَّع إلا رسائل البوت الصادرة. تُتخطّى القنوات (channel) فقط؛ أمّا
    المجموعات فيُسمح فيها للبوت بحذف رسائله، لذا تُتتبَّع وتُنظَّف عبر /clean.
    """
    # إذا عرفنا نوع الشات مسبقاً، نتخطى التتبع في المجموعات
    if chat_type and chat_type in _PROTECTED_CHAT_TYPES:
        return

    key = f"chat_msgs_{chat_id}"
    # تخزين القاموس: {message_id: timestamp} بدلاً من list
    # للسماح بحذف الرسائل القديمة حسب TTL
    msgs = context.bot_data.get(key, {})
    if not isinstance(msgs, dict):
        # ترحيل من تنسيق list قديم
        msgs = {mid: time.time() for mid in msgs}
    msgs[message_id] = time.time()

    # تنظيف الرسائل التي تجاوزت TTL (lazy cleanup)
    cutoff = time.time() - CHAT_MSGS_TTL_SECONDS
    stale_msgs = [mid for mid, ts in msgs.items() if ts < cutoff]
    for mid in stale_msgs:
        del msgs[mid]

    # حد أقصى للعدد (الأحدث أولاً)
    if len(msgs) > MAX_TRACKED_MSGS:
        cutoff_time = sorted(msgs.values(), reverse=True)[MAX_TRACKED_MSGS - 1]
        msgs = {mid: ts for mid, ts in msgs.items() if ts >= cutoff_time}

    context.bot_data[key] = msgs
    _stats["messages_tracked"] += 1


async def clean_chat_messages(context, chat_id, chat_type=None):
    """Delete all tracked (bot) messages for a chat and remove them from tracking.

    تُتخطّى القنوات (channel) بالكامل. في المجموعات/السوبر-جروب يُسمح للبوت بحذف
    رسائله الصادرة فيُنظَّف ما تتبَّع منه. رسائل المستخدمين لا تُمسّ هنا.
    """
    if chat_type and chat_type in _PROTECTED_CHAT_TYPES:
        return
    cached_type = context.bot_data.get(f"_chat_type_{chat_id}")
    if cached_type and cached_type in _PROTECTED_CHAT_TYPES:
        return

    key = f"chat_msgs_{chat_id}"
    msgs = context.bot_data.pop(key, {})
    if not isinstance(msgs, dict):
        msgs = {}

    _stats["cleanup_runs"] += 1
    deleted_count = 0
    for chunk in _chunks(list(msgs.keys()), DELETE_MESSAGES_CHUNK):
        deleted_count += await _delete_message_ids(context, chat_id, chunk)

    _stats["messages_deleted"] += deleted_count


def _chunks(items, size):
    """Yield successive chunks of ``items`` bounded by ``size`` elements."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _delete_message_ids(context, chat_id, message_ids):
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
    return deleted


def _delete_job_name(chat_id, message_id):
    return f"del_{chat_id}_{message_id}"


async def schedule_delete(context, chat_id, message_id, delay=DELETE_DELAY):
    """Schedule automatic deletion of a message after a delay in seconds."""
    if not message_id:
        return
    job_name = _delete_job_name(chat_id, message_id)
    existing = context.job_queue.get_jobs_by_name(job_name)
    for j in existing:
        j.schedule_removal()
    context.job_queue.run_once(
        _delete_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=job_name,
    )


async def _delete_job(context):
    data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
        )
        _stats["messages_deleted"] += 1
    except Exception as e:
        logger.debug(f"Delete failed: {e}")


async def delete_now(context, chat_id, message_id):
    """Immediately delete a specific message, ignoring errors silently."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        _stats["messages_deleted"] += 1
    except Exception as e:
        logger.debug(f"delete_now failed: {e}")


def track_message(context, chat_id, message_id):
    """Register an already-sent message for future cleanup via /clean."""
    _track_msg(context, chat_id, message_id)


async def clean_command(update, context):
    """Delete the user's command message that triggered this handler."""
    if update.message:
        await delete_now(context, update.effective_chat.id, update.message.message_id)


async def send_and_track(context, chat_id, text, keyboard=None, parse_mode="HTML"):
    """Send a message and track it for cleanup — unified helper."""
    msg = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=parse_mode
    )
    _track_msg(context, chat_id, msg.message_id)
    return msg


async def send_loading(update, context, text="⏳ جاري العمل..."):
    """Send a loading indicator message and track it for future cleanup."""
    chat_id = update.effective_chat.id
    # الرسالة عابرة (مؤشر تحميل) — لا نطلق إشعاراً للمستخدم
    msg = await context.bot.send_message(
        chat_id=chat_id, text=text, disable_notification=True
    )
    _track_msg(context, chat_id, msg.message_id)
    return msg


def _truncate(text: str) -> str:
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH - len(MESSAGE_TRUNCATION_SUFFIX)] + MESSAGE_TRUNCATION_SUFFIX
    return text


async def safe_edit_or_send(query, context, text, keyboard=None):
    """Edit the callback message in place; fall back to a new message if edit fails.

    Handles the case where the original message was deleted (e.g., by /clean or
    a previous send_step) — instead of a silent no-op, a fresh message is sent
    so the user always gets a visible response.
    """
    text = _truncate(text)
    chat_id = query.message.chat_id
    try:
        msg = await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        if msg:
            _track_msg(context, chat_id, msg.message_id)
            context.user_data["last_msg"] = msg.message_id
        return msg
    except Exception as e:
        err = str(e)
        if _is_benign_edit_error(e):
            prev = context.user_data.pop("last_msg", None)
            if prev:
                await delete_now(context, chat_id, prev)
            msg = await context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
            )
            _track_msg(context, chat_id, msg.message_id)
            context.user_data["last_msg"] = msg.message_id
            return msg
        raise


async def edit_clean(query, context, text, keyboard=None):
    """Edit a callback query message with new text and track the edit for cleanup."""
    text = _truncate(text)
    try:
        msg = await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        if _is_benign_edit_error(e):
            # المحتوى لم يتغير أو الرسالة محذوفة — حالة حميدة، نتجاهلها بصمت
            logger.debug(f"edit_clean benign skip: {e}")
            return None
        raise
    if msg is not None:
        _track_msg(context, query.message.chat_id, msg.message_id)
        context.user_data["last_msg"] = msg.message_id
    return msg


async def safe_edit_plain(query, context, text, reply_markup=None):
    """عدّل رسالة الاستدعاء مع تجاهل أخطاء التعديل الحميدة.

    يُبقي على parse_mode الافتراضي (بدون HTML) المستخدم في الاستدعاءات المباشرة
    لـ ``query.edit_message_text``، ويتجاهل أخطاء مثل "Message is not modified"
    دون إنهاء تدفق المحادثة.
    """
    try:
        msg = await query.edit_message_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        if _is_benign_edit_error(e):
            logger.debug(f"safe_edit_plain benign skip: {e}")
            return None
        raise
    if msg is not None:
        _track_msg(context, query.message.chat_id, msg.message_id)
        context.user_data["last_msg"] = msg.message_id
    return msg


async def _send_replacing_last(update, context, text, keyboard) -> object:
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
    if prev:
        await delete_now(context, chat_id, prev)
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")
    _track_msg(context, chat_id, msg.message_id)
    return msg


async def send_step(update, context, text, keyboard=None):
    """Send a new step message while cleaning up the previous step message."""
    text = _truncate(text)
    msg = await _send_replacing_last(update, context, text, keyboard)
    context.user_data["last_msg"] = msg.message_id
    return msg


async def reply_final(update, context, text, keyboard=None):
    """Send a final reply message while cleaning up the previous step message."""
    text = _truncate(text)
    await _send_replacing_last(update, context, text, keyboard)


def get_cleanup_stats() -> dict:
    """إرجاع إحصائيات الأداء للمراقبة."""
    return _stats.copy()
