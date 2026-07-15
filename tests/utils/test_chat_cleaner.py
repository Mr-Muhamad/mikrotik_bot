"""Tests for utils.chat_cleaner — message tracking, cleanup, and truncation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.chat_cleaner import (
    MAX_MESSAGE_LENGTH,
    MAX_TRACKED_MSGS,
    clean_chat_messages,
    clean_command,
    delete_now,
    edit_clean,
    reply_final,
    schedule_delete,
    send_loading,
    send_step,
)


def _ctx(chat_id: int = 1, job_queue=None, user_data=None, bot_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = bot_data if bot_data is not None else {}
    if job_queue is None:
        job_queue = MagicMock()
        job_queue.get_jobs_by_name = MagicMock(return_value=[])
        job_queue.run_once = MagicMock()
    ctx.job_queue = job_queue
    ctx.bot = MagicMock()
    ctx.bot.delete_message = AsyncMock()
    ctx.bot.delete_messages = AsyncMock(return_value=True)
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=100))
    return ctx


def _update(text: str = "/clean", callback_data: str | None = None):
    update = MagicMock()
    update.message = MagicMock()
    update.message.message_id = 50
    update.message.text = text
    update.effective_chat = MagicMock(id=1, type="private")
    if callback_data is not None:
        update.callback_query = MagicMock()
        update.callback_query.data = callback_data
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 1
        update.callback_query.message.message_id = 60
        update.callback_query.edit_message_text = AsyncMock(
            return_value=MagicMock(message_id=61)
        )
    return update


# ─── Tracking tests ────────────────────────────────────────────


class TestCleanChatMessages:
    @pytest.mark.asyncio
    async def test_no_tracked_messages(self):
        ctx = _ctx()
        await clean_chat_messages(ctx, 1)
        ctx.bot.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_batch_delete(self):
        ctx = _ctx(bot_data={"chat_msgs_1": {10: 0.0, 20: 0.0, 30: 0.0}})
        await clean_chat_messages(ctx, 1)
        ctx.bot.delete_messages.assert_called_once()
        called = ctx.bot.delete_messages.call_args.kwargs
        assert set(called["message_ids"]) == {10, 20, 30}
        assert "chat_msgs_1" not in ctx.bot_data

    @pytest.mark.asyncio
    async def test_splits_large_chat_into_chunks(self):
        ids = {i: 0.0 for i in range(250)}
        ctx = _ctx(bot_data={"chat_msgs_1": ids})
        await clean_chat_messages(ctx, 1)
        # 250 tracked messages -> 3 batches (100 + 100 + 50)
        assert ctx.bot.delete_messages.call_count == 3
        assert "chat_msgs_1" not in ctx.bot_data

    @pytest.mark.asyncio
    async def test_swallows_delete_errors(self):
        ctx = _ctx(bot_data={"chat_msgs_1": {10: 0.0, 20: 0.0}})
        # الحذف الجماعي يفشل ثم يتراجع فردياً مع فشل كل رسالة — يجب ألا يرمي
        ctx.bot.delete_messages = AsyncMock(side_effect=Exception("rate limit"))
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("gone"))
        await clean_chat_messages(ctx, 1)  # must not raise

    @pytest.mark.asyncio
    async def test_cleans_bot_messages_in_group(self):
        ctx = _ctx(bot_data={"chat_msgs_1": {10: 0.0, 20: 0.0}})
        await clean_chat_messages(ctx, 1, chat_type="group")
        ctx.bot.delete_messages.assert_called_once()
        assert "chat_msgs_1" not in ctx.bot_data

    @pytest.mark.asyncio
    async def test_skips_channel_cleanup(self):
        ctx = _ctx(bot_data={"chat_msgs_1": {10: 0.0, 20: 0.0}})
        await clean_chat_messages(ctx, 1, chat_type="channel")
        ctx.bot.delete_message.assert_not_called()
        ctx.bot.delete_messages.assert_not_called()
        assert "chat_msgs_1" in ctx.bot_data


# ─── Schedule delete tests ─────────────────────────────────────


class TestScheduleDelete:
    @pytest.mark.asyncio
    async def test_skips_when_no_message_id(self):
        ctx = _ctx()
        await schedule_delete(ctx, 1, None, delay=5)
        ctx.job_queue.run_once.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedules_run_once(self):
        ctx = _ctx()
        await schedule_delete(ctx, 1, 100, delay=10)
        ctx.job_queue.run_once.assert_called_once()
        call_kwargs = ctx.job_queue.run_once.call_args.kwargs
        assert call_kwargs["when"] == 10
        assert call_kwargs["data"]["message_id"] == 100

    @pytest.mark.asyncio
    async def test_cancels_existing_job_with_same_name(self):
        existing_job = MagicMock()
        ctx = _ctx(job_queue=MagicMock(
            get_jobs_by_name=MagicMock(return_value=[existing_job]),
            run_once=MagicMock(),
        ))
        await schedule_delete(ctx, 1, 100)
        existing_job.schedule_removal.assert_called_once()


# ─── Delete now tests ──────────────────────────────────────────


class TestDeleteNow:
    @pytest.mark.asyncio
    async def test_deletes_message(self):
        ctx = _ctx()
        await delete_now(ctx, 1, 100)
        ctx.bot.delete_message.assert_called_once_with(chat_id=1, message_id=100)

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        ctx = _ctx()
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("nope"))
        await delete_now(ctx, 1, 100)  # must not raise


# ─── clean_command tests ───────────────────────────────────────


class TestCleanCommand:
    @pytest.mark.asyncio
    async def test_deletes_user_message(self):
        ctx = _ctx()
        update = _update()
        await clean_command(update, ctx)
        ctx.bot.delete_message.assert_called_once_with(chat_id=1, message_id=50)

    @pytest.mark.asyncio
    async def test_no_op_without_message(self):
        ctx = _ctx()
        update = MagicMock()
        update.message = None
        await clean_command(update, ctx)
        ctx.bot.delete_message.assert_not_called()


# ─── send_loading tests ────────────────────────────────────────


class TestSendLoading:
    @pytest.mark.asyncio
    async def test_sends_and_tracks(self):
        ctx = _ctx()
        update = _update()
        await send_loading(update, ctx, "⏳ working...")
        ctx.bot.send_message.assert_called_once_with(
        chat_id=1, text="⏳ working...", disable_notification=True
    )
        assert 100 in ctx.bot_data["chat_msgs_1"]


# ─── edit_clean tests ──────────────────────────────────────────


class TestEditClean:
    @pytest.mark.asyncio
    async def test_truncates_long_text(self):
        ctx = _ctx()
        update = _update(callback_data="any")
        long_text = "x" * (MAX_MESSAGE_LENGTH + 100)
        await edit_clean(update.callback_query, ctx, long_text)
        called_text = update.callback_query.edit_message_text.call_args.kwargs["text"]
        assert len(called_text) <= MAX_MESSAGE_LENGTH
        assert "تم اقتطاع" in called_text

    @pytest.mark.asyncio
    async def test_tracks_edited_message(self):
        ctx = _ctx()
        update = _update(callback_data="any")
        await edit_clean(update.callback_query, ctx, "hello")
        assert 61 in ctx.bot_data["chat_msgs_1"]
        assert ctx.user_data["last_msg"] == 61

    @pytest.mark.asyncio
    async def test_handles_none_return(self):
        ctx = _ctx()
        update = _update(callback_data="any")
        update.callback_query.edit_message_text = AsyncMock(return_value=None)
        await edit_clean(update.callback_query, ctx, "hello")
        # bot_data should not have the chat_msgs_1 key (or be empty)
        assert ctx.bot_data.get("chat_msgs_1", []) == []


# ─── send_step tests ───────────────────────────────────────────


class TestSendStep:
    @pytest.mark.asyncio
    async def test_deletes_user_message_then_sends(self):
        ctx = _ctx()
        update = _update()
        await send_step(update, ctx, "step1", keyboard=None)
        # First call: delete the user message
        ctx.bot.delete_message.assert_any_call(chat_id=1, message_id=50)
        # Then send
        ctx.bot.send_message.assert_called_once()
        assert ctx.user_data["last_msg"] == 100
        assert 100 in ctx.bot_data["chat_msgs_1"]

    @pytest.mark.asyncio
    async def test_deletes_previous_step(self):
        ctx = _ctx(user_data={"last_msg": 99})
        update = _update()
        await send_step(update, ctx, "step2")
        # delete previous step
        ctx.bot.delete_message.assert_any_call(chat_id=1, message_id=99)
        assert ctx.user_data["last_msg"] == 100

    @pytest.mark.asyncio
    async def test_skips_user_message_in_group(self):
        ctx = _ctx()
        update = _update()
        update.effective_chat.type = "group"
        await send_step(update, ctx, "step1", keyboard=None)
        # لا يحذف البوت رسالة المستخدم في المجموعة (صلاحية غير متاحة)
        user_msg_calls = [
            c for c in ctx.bot.delete_message.call_args_list
            if c.kwargs.get("message_id") == 50
        ]
        assert user_msg_calls == []
        # لكنه لا يزال يرسل رسالته الخاصة
        ctx.bot.send_message.assert_called_once()


# ─── reply_final tests ────────────────────────────────────────


class TestReplyFinal:
    @pytest.mark.asyncio
    async def test_truncates_and_sends(self):
        ctx = _ctx()
        update = _update()
        long_text = "y" * (MAX_MESSAGE_LENGTH + 50)
        await reply_final(update, ctx, long_text)
        called_text = ctx.bot.send_message.call_args.kwargs["text"]
        assert len(called_text) <= MAX_MESSAGE_LENGTH

    @pytest.mark.asyncio
    async def test_tracks_message(self):
        ctx = _ctx()
        update = _update()
        await reply_final(update, ctx, "final")
        # Note: reply_final does NOT save last_msg (only send_step does)
        assert ctx.user_data.get("last_msg") is None
        assert 100 in ctx.bot_data["chat_msgs_1"]

    @pytest.mark.asyncio
    async def test_cleans_previous_step(self):
        ctx = _ctx(user_data={"last_msg": 99})
        update = _update()
        await reply_final(update, ctx, "final")
        ctx.bot.delete_message.assert_any_call(chat_id=1, message_id=99)
        # New message tracked
        assert 100 in ctx.bot_data["chat_msgs_1"]


# ─── Trim threshold tests ──────────────────────────────────────


class TestTrackingTrim:
    @pytest.mark.asyncio
    async def test_trims_when_over_max(self):
        # Pre-fill tracking to at the limit (dict format: {message_id: timestamp})
        existing = {i: 0.0 for i in range(1, MAX_TRACKED_MSGS + 1)}
        ctx = _ctx(bot_data={"chat_msgs_1": existing})
        update = _update()
        # Add one more (triggers trim)
        await send_loading(update, ctx, "⏳ extra")
        # After trim: keep at most MAX_TRACKED_MSGS entries
        assert len(ctx.bot_data["chat_msgs_1"]) <= MAX_TRACKED_MSGS
        # New message (100) should be tracked
        assert 100 in ctx.bot_data["chat_msgs_1"]
