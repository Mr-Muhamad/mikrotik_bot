import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message


def _run(coro):  # type: ignore[reportMissingParameterType]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _ctx(job_queue=None, user_data=None, bot_data=None):  # type: ignore[reportMissingParameterType]
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
    ctx.bot.send_message = AsyncMock(
        return_value=Message(
            message_id=200,
            date=datetime.now(UTC),
            chat=Chat(id=10, type="private"),
        )
    )
    return ctx


def _update(text="/clean", chat_type="private", msg_id=50):  # type: ignore[reportMissingParameterType]
    update = MagicMock()
    update.message = MagicMock()
    update.message.message_id = msg_id
    update.message.text = text
    update.effective_chat = MagicMock(id=10, type=chat_type)
    return update


def _callback_query(chat_id=10, msg_id=60):  # type: ignore[reportMissingParameterType]
    query = MagicMock()
    query.message = MagicMock()
    query.message.chat_id = chat_id
    query.message.message_id = msg_id
    query.edit_message_text = AsyncMock(
        return_value=Message(
            message_id=70,
            date=datetime.now(UTC),
            chat=Chat(id=chat_id, type="private"),
        )
    )
    return query


class TestIsBenignEditError:
    def test_matches_not_modified(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("Message is not modified")) is True

    def test_matches_not_found(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("Message to edit not found")) is True

    def test_matches_same_content(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("message is exactly the same as before")) is True

    def test_no_match_on_unrelated_error(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("Flood control exceeded")) is False

    def test_no_match_on_empty_string(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("")) is False

    def test_partial_match_inside_longer_message(self):
        from utils.chat_cleaner import _is_benign_edit_error  # type: ignore[reportPrivateUsage]

        assert _is_benign_edit_error(Exception("Error: Message to edit not found (404)")) is True


class TestTrackMsg:
    def test_skips_channel_type(self):
        from utils.chat_cleaner import _track_msg  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        with patch("database.models.add_tracked_message") as mock_add:
            _track_msg(ctx, 1, 10, chat_type="channel")
            mock_add.assert_not_called()

    def test_proceeds_with_none_type(self):
        from utils.chat_cleaner import _track_msg  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        with patch("database.models.add_tracked_message") as mock_add:
            _track_msg(ctx, 1, 10, chat_type=None)
            mock_add.assert_called_once_with(1, 10)

    def test_proceeds_with_group_type(self):
        from utils.chat_cleaner import _track_msg  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        with patch("database.models.add_tracked_message") as mock_add:
            _track_msg(ctx, 1, 10, chat_type="group")
            mock_add.assert_called_once_with(1, 10)

    def test_proceeds_with_private_type(self):
        from utils.chat_cleaner import _track_msg  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        with patch("database.models.add_tracked_message") as mock_add:
            _track_msg(ctx, 1, 10, chat_type="private")
            mock_add.assert_called_once_with(1, 10)

    def test_proceeds_without_chat_type_argument(self):
        from utils.chat_cleaner import _track_msg  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        with patch("database.models.add_tracked_message") as mock_add:
            _track_msg(ctx, 1, 10)
            mock_add.assert_called_once_with(1, 10)


class TestTrackMsgStats:
    def test_increments_stats_counter(self):
        from utils.chat_cleaner import _track_msg, get_cleanup_stats  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        before = get_cleanup_stats()["messages_tracked"]
        with patch("database.models.add_tracked_message"):
            _track_msg(ctx, 1, 99)
        after = get_cleanup_stats()["messages_tracked"]
        assert after == before + 1

    def test_channel_skip_does_not_increment(self):
        from utils.chat_cleaner import _track_msg, get_cleanup_stats  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        before = get_cleanup_stats()["messages_tracked"]
        with patch("database.models.add_tracked_message"):
            _track_msg(ctx, 1, 99, chat_type="channel")
        after = get_cleanup_stats()["messages_tracked"]
        assert after == before


class TestTrackMessagePublicWrapper:
    def test_calls_track_msg(self):
        from utils.chat_cleaner import track_message

        ctx = _ctx()
        with patch("utils.chat_cleaner._track_msg") as mock_inner:
            track_message(ctx, 5, 42)
            mock_inner.assert_called_once_with(ctx, 5, 42)


class TestChunks:
    def test_exact_division(self):
        from utils.chat_cleaner import _chunks  # type: ignore[reportPrivateUsage]

        result = list(_chunks([1, 2, 3, 4], 2))
        assert result == [[1, 2], [3, 4]]

    def test_remainder(self):
        from utils.chat_cleaner import _chunks  # type: ignore[reportPrivateUsage]

        result = list(_chunks([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_single_chunk(self):
        from utils.chat_cleaner import _chunks  # type: ignore[reportPrivateUsage]

        result = list(_chunks([1, 2, 3], 10))
        assert result == [[1, 2, 3]]

    def test_empty_sequence(self):
        from utils.chat_cleaner import _chunks  # type: ignore[reportPrivateUsage]

        result = list(_chunks([], 5))
        assert result == []

    def test_size_one(self):
        from utils.chat_cleaner import _chunks  # type: ignore[reportPrivateUsage]

        result = list(_chunks([10, 20, 30], 1))
        assert result == [[10], [20], [30]]


class TestDeleteMessageIds:
    def test_empty_list_returns_zero(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        result = _run(_delete_message_ids(ctx, 1, []))
        assert result == 0

    def test_single_message_success(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        result = _run(_delete_message_ids(ctx, 1, [42]))
        assert result == 1
        ctx.bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=42)

    def test_single_message_failure(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("gone"))
        result = _run(_delete_message_ids(ctx, 1, [42]))
        assert result == 0

    def test_batch_success(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.bot.delete_messages = AsyncMock(return_value=True)
        result = _run(_delete_message_ids(ctx, 1, [10, 20, 30]))
        assert result == 3
        ctx.bot.delete_messages.assert_awaited_once_with(chat_id=1, message_ids=[10, 20, 30])

    def test_batch_returns_non_true_falls_back(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.bot.delete_messages = AsyncMock(return_value=False)
        ctx.bot.delete_message = AsyncMock()
        result = _run(_delete_message_ids(ctx, 1, [10, 20]))
        assert result == 2
        assert ctx.bot.delete_message.await_count == 2

    def test_batch_exception_falls_back(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.bot.delete_messages = AsyncMock(side_effect=Exception("API error"))
        ctx.bot.delete_message = AsyncMock()
        result = _run(_delete_message_ids(ctx, 1, [10, 20]))
        assert result == 2

    def test_batch_partial_individual_failure(self):
        from utils.chat_cleaner import _delete_message_ids  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.bot.delete_messages = AsyncMock(side_effect=Exception("fail"))
        ctx.bot.delete_message = AsyncMock(
            side_effect=[None, Exception("gone")]
        )
        result = _run(_delete_message_ids(ctx, 1, [10, 20]))
        assert result == 1


class TestDeleteJobName:
    def test_format(self):
        from utils.chat_cleaner import _delete_job_name  # type: ignore[reportPrivateUsage]

        assert _delete_job_name(123, 456) == "del_123_456"

    def test_zero_ids(self):
        from utils.chat_cleaner import _delete_job_name  # type: ignore[reportPrivateUsage]

        assert _delete_job_name(0, 0) == "del_0_0"


class TestDeleteJob:
    def test_success(self):
        from utils.chat_cleaner import _delete_job, get_cleanup_stats  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.job = MagicMock()
        ctx.job.data = {"chat_id": 10, "message_id": 55}
        before = get_cleanup_stats()["messages_deleted"]
        _run(_delete_job(ctx))
        ctx.bot.delete_message.assert_awaited_once_with(chat_id="10", message_id=55)
        assert get_cleanup_stats()["messages_deleted"] == before + 1

    def test_failure_swallows_exception(self):
        from utils.chat_cleaner import _delete_job  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        ctx.job = MagicMock()
        ctx.job.data = {"chat_id": 10, "message_id": 55}
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("forbidden"))
        _run(_delete_job(ctx))


class TestSendAndTrack:
    def test_sends_and_tracks(self):
        from utils.chat_cleaner import send_and_track

        ctx = _ctx()
        result = _run(send_and_track(ctx, 10, "hello", parse_mode="HTML"))
        ctx.bot.send_message.assert_awaited_once_with(
            chat_id=10, text="hello", reply_markup=None, parse_mode="HTML"
        )
        assert result.message_id == 200

    def test_with_keyboard(self):
        from utils.chat_cleaner import send_and_track

        ctx = _ctx()
        kb = MagicMock()
        _run(send_and_track(ctx, 10, "hi", keyboard=kb))
        ctx.bot.send_message.assert_awaited_once_with(
            chat_id=10, text="hi", reply_markup=kb, parse_mode="HTML"
        )

    def test_with_custom_parse_mode(self):
        from utils.chat_cleaner import send_and_track

        ctx = _ctx()
        _run(send_and_track(ctx, 10, "text", parse_mode="Markdown"))
        call_kwargs = ctx.bot.send_message.call_args.kwargs
        assert call_kwargs["parse_mode"] == "Markdown"


class TestSafeEditOrSend:
    def test_none_query_returns_none(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        result = _run(safe_edit_or_send(None, ctx, "text"))
        assert result is None

    def test_none_message_returns_none(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = MagicMock()
        query.message = None
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert result is None

    def test_no_chat_id_returns_none(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = None
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert result is None

    def test_zero_chat_id_returns_none(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 0
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert result is None

    def test_successful_edit(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        result = _run(safe_edit_or_send(query, ctx, "new text"))
        query.edit_message_text.assert_awaited_once()
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 70

    def test_successful_edit_returns_none_for_non_message(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(return_value=None)
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert result is None

    def test_benign_error_with_prev_msg(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx(user_data={"last_msg": 88})
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message is not modified")
        )
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert ctx.bot.delete_message.await_count >= 1
        ctx.bot.delete_message.assert_any_await(chat_id=10, message_id=88)
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 200

    def test_benign_error_without_prev_msg(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message to edit not found")
        )
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 200

    def test_non_benign_error_raises(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Unauthorized: bot was blocked")
        )
        with pytest.raises(Exception, match="Unauthorized"):
            _run(safe_edit_or_send(query, ctx, "text"))

    def test_truncates_long_text(self):
        from utils.chat_cleaner import MAX_MESSAGE_LENGTH, safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        long = "A" * (MAX_MESSAGE_LENGTH + 500)
        _run(safe_edit_or_send(query, ctx, long))
        called_text = query.edit_message_text.call_args.kwargs["text"]
        assert len(called_text) <= MAX_MESSAGE_LENGTH
        assert "تم اقتطاع" in called_text

    def test_non_message_return_does_not_track(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(return_value="not a message")
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert result is None
        assert "last_msg" not in ctx.user_data


class TestSafeEditPlain:
    def test_none_query_returns_none(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        result = _run(safe_edit_plain(None, ctx, "text"))
        assert result is None

    def test_none_message_proceeds_to_edit(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = MagicMock()
        query.message = None
        query.edit_message_text = AsyncMock(return_value="result")
        result = _run(safe_edit_plain(query, ctx, "text"))
        query.edit_message_text.assert_awaited_once()
        assert result is None

    def test_chat_id_zero_returns_none(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 0
        result = _run(safe_edit_plain(query, ctx, "text"))
        assert result is None

    def test_successful_edit(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        result = _run(safe_edit_plain(query, ctx, "plain text"))
        query.edit_message_text.assert_awaited_once_with(
            text="plain text", reply_markup=None
        )
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 70

    def test_benign_error_returns_none(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message is not modified")
        )
        result = _run(safe_edit_plain(query, ctx, "text"))
        assert result is None

    def test_non_benign_error_raises(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Bad Request: message to edit not found")
        )
        with pytest.raises(Exception, match="Bad Request"):
            _run(safe_edit_plain(query, ctx, "text"))

    def test_non_message_return(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(return_value=None)
        result = _run(safe_edit_plain(query, ctx, "text"))
        assert result is None

    def test_with_reply_markup(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        kb = MagicMock()
        _run(safe_edit_plain(query, ctx, "text", reply_markup=kb))
        call_kwargs = query.edit_message_text.call_args.kwargs
        assert call_kwargs["reply_markup"] is kb

    def test_no_parse_mode_in_call(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        _run(safe_edit_plain(query, ctx, "text"))
        call_kwargs = query.edit_message_text.call_args.kwargs
        assert "parse_mode" not in call_kwargs


class TestEditCleanExtended:
    def test_none_query_returns_none(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        result = _run(edit_clean(None, ctx, "text"))
        assert result is None

    def test_chat_id_zero_returns_none(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = MagicMock()
        query.message = MagicMock()
        query.message.chat_id = 0
        result = _run(edit_clean(query, ctx, "text"))
        assert result is None

    def test_non_message_return(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(return_value=None)
        result = _run(edit_clean(query, ctx, "text"))
        assert result is None

    def test_benign_not_modified_error(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message is not modified")
        )
        result = _run(edit_clean(query, ctx, "text"))
        assert result is None

    def test_benign_not_found_error(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message to edit not found")
        )
        result = _run(edit_clean(query, ctx, "text"))
        assert result is None

    def test_non_benign_error_raises(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("FloodWaitError: wait 30 seconds")
        )
        with pytest.raises(Exception, match="FloodWaitError"):
            _run(edit_clean(query, ctx, "text"))

    def test_successful_edit_returns_message(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        result = _run(edit_clean(query, ctx, "updated"))
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 70

    def test_truncates_long_text(self):
        from utils.chat_cleaner import MAX_MESSAGE_LENGTH, edit_clean

        ctx = _ctx()
        query = _callback_query()
        long = "Z" * (MAX_MESSAGE_LENGTH + 200)
        _run(edit_clean(query, ctx, long))
        called_text = query.edit_message_text.call_args.kwargs["text"]
        assert len(called_text) <= MAX_MESSAGE_LENGTH

    def test_with_keyboard(self):
        from utils.chat_cleaner import edit_clean

        ctx = _ctx()
        query = _callback_query()
        kb = MagicMock()
        _run(edit_clean(query, ctx, "text", keyboard=kb))
        call_kwargs = query.edit_message_text.call_args.kwargs
        assert call_kwargs["reply_markup"] is kb
        assert call_kwargs["parse_mode"] == "HTML"


class TestCleanChatMessagesExtended:
    def test_chat_type_channel_skips(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx()
        with patch("database.models.get_tracked_messages") as mock_get:
            _run(clean_chat_messages(ctx, 1, chat_type="channel"))
            mock_get.assert_not_called()

    def test_cached_type_channel_skips(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx(bot_data={"_chat_type_1": "channel"})
        with patch("database.models.get_tracked_messages") as mock_get:
            _run(clean_chat_messages(ctx, 1))
            mock_get.assert_not_called()

    def test_cached_type_supergroup_proceeds(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx(bot_data={"_chat_type_1": "supergroup"})
        with (
            patch("database.models.get_tracked_messages", return_value=None) as mock_get,
            patch("database.models.remove_tracked_messages"),
        ):
            _run(clean_chat_messages(ctx, 1, chat_type="supergroup"))
            mock_get.assert_called_once_with(1)

    def test_no_tracked_messages_returns_early(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx()
        with (
            patch("database.models.get_tracked_messages", return_value=None),
            patch("database.models.remove_tracked_messages") as mock_remove,
        ):
            _run(clean_chat_messages(ctx, 1))
            mock_remove.assert_not_called()

    def test_empty_tracked_list_returns_early(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx()
        with (
            patch("database.models.get_tracked_messages", return_value=[]),
            patch("database.models.remove_tracked_messages") as mock_remove,
        ):
            _run(clean_chat_messages(ctx, 1))
            mock_remove.assert_not_called()

    def test_increments_cleanup_runs(self):
        from utils.chat_cleaner import clean_chat_messages, get_cleanup_stats

        ctx = _ctx()
        before = get_cleanup_stats()["cleanup_runs"]
        with (
            patch("database.models.get_tracked_messages", return_value=[10, 20]),
            patch("database.models.remove_tracked_messages"),
        ):
            _run(clean_chat_messages(ctx, 1))
        assert get_cleanup_stats()["cleanup_runs"] == before + 1

    def test_supergroup_type_not_protected(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx()
        with (
            patch("database.models.get_tracked_messages", return_value=[5]) as mock_get,
            patch("database.models.remove_tracked_messages"),
        ):
            _run(clean_chat_messages(ctx, 1, chat_type="supergroup"))
            mock_get.assert_called_once_with(1)

    def test_remove_called_even_on_telegram_failure(self):
        from utils.chat_cleaner import clean_chat_messages

        ctx = _ctx()
        ctx.bot.delete_messages = AsyncMock(side_effect=Exception("network error"))
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("network error"))
        with (
            patch("database.models.get_tracked_messages", return_value=[10, 20]),
            patch("database.models.remove_tracked_messages") as mock_remove,
        ):
            _run(clean_chat_messages(ctx, 1))
            mock_remove.assert_called()


class TestSendReplacingLast:
    def test_private_chat_deletes_user_message(self):
        from utils.chat_cleaner import _send_replacing_last  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        update = _update(chat_type="private")
        _run(_send_replacing_last(update, ctx, "text", None))
        ctx.bot.delete_message.assert_any_await(chat_id=10, message_id=50)

    def test_non_private_chat_skips_user_message(self):
        from utils.chat_cleaner import _send_replacing_last  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        update = _update(chat_type="group")
        _run(_send_replacing_last(update, ctx, "text", None))
        delete_calls = [
            c
            for c in ctx.bot.delete_message.await_call_list
            if c.kwargs.get("message_id") == 50
        ]
        assert len(delete_calls) == 0
        ctx.bot.send_message.assert_awaited_once()

    def test_deletes_previous_last_msg(self):
        from utils.chat_cleaner import _send_replacing_last  # type: ignore[reportPrivateUsage]

        ctx = _ctx(user_data={"last_msg": 99})
        update = _update()
        _run(_send_replacing_last(update, ctx, "text", None))
        ctx.bot.delete_message.assert_any_await(chat_id=10, message_id=99)

    def test_sends_new_message(self):
        from utils.chat_cleaner import _send_replacing_last  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        update = _update()
        _run(_send_replacing_last(update, ctx, "new", None))
        ctx.bot.send_message.assert_awaited_once_with(
            chat_id=10, text="new", reply_markup=None, parse_mode="HTML"
        )

    def test_channel_type_skips_user_message(self):
        from utils.chat_cleaner import _send_replacing_last  # type: ignore[reportPrivateUsage]

        ctx = _ctx()
        update = _update(chat_type="channel")
        _run(_send_replacing_last(update, ctx, "text", None))
        delete_calls = ctx.bot.delete_message.await_call_list
        for c in delete_calls:
            assert c.kwargs.get("message_id") != 50


class TestRunBackgroundCleanup:
    def test_calls_delete_stale_and_health_cleanup(self):
        from utils.chat_cleaner import run_background_cleanup

        ctx = _ctx()
        with (
            patch("database.models.delete_stale_records") as mock_stale,
            patch("database.models.cleanup_health_history", return_value=0) as mock_health,
            patch("database.models.UTC_TIMESTAMP_FORMAT", "%Y-%m-%d %H:%M:%S"),
        ):
            _run(run_background_cleanup(ctx))
            mock_stale.assert_called_once()
            mock_health.assert_called_once_with(days=7)

    def test_logs_when_health_cleaned(self):
        from utils.chat_cleaner import run_background_cleanup

        ctx = _ctx()
        with (
            patch("database.models.delete_stale_records"),
            patch("database.models.cleanup_health_history", return_value=5),
            patch("database.models.UTC_TIMESTAMP_FORMAT", "%Y-%m-%d %H:%M:%S"),
            patch("utils.chat_cleaner.logger") as mock_logger,
        ):
            _run(run_background_cleanup(ctx))
            mock_logger.debug.assert_called_once()


class TestGetCleanupStats:
    def test_returns_copy_not_reference(self):
        from utils.chat_cleaner import get_cleanup_stats

        stats1 = get_cleanup_stats()
        stats2 = get_cleanup_stats()
        assert stats1 == stats2
        stats1["messages_tracked"] = 99999
        assert get_cleanup_stats()["messages_tracked"] != 99999

    def test_has_expected_keys(self):
        from utils.chat_cleaner import get_cleanup_stats

        stats = get_cleanup_stats()
        assert "messages_tracked" in stats
        assert "messages_deleted" in stats
        assert "cleanup_runs" in stats


class TestDeleteNowExtended:
    def test_increments_stats_on_success(self):
        from utils.chat_cleaner import delete_now, get_cleanup_stats

        ctx = _ctx()
        before = get_cleanup_stats()["messages_deleted"]
        _run(delete_now(ctx, 1, 100))
        assert get_cleanup_stats()["messages_deleted"] == before + 1

    def test_does_not_increment_stats_on_failure(self):
        from utils.chat_cleaner import delete_now, get_cleanup_stats

        ctx = _ctx()
        ctx.bot.delete_message = AsyncMock(side_effect=Exception("forbidden"))
        before = get_cleanup_stats()["messages_deleted"]
        _run(delete_now(ctx, 1, 100))
        assert get_cleanup_stats()["messages_deleted"] == before


class TestSendLoadingExtended:
    def test_default_loading_text(self):
        from utils.chat_cleaner import send_loading

        ctx = _ctx()
        update = _update()
        _run(send_loading(update, ctx))
        call_kwargs = ctx.bot.send_message.call_args.kwargs
        assert call_kwargs["text"] == "⏳ جاري العمل..."
        assert call_kwargs["disable_notification"] is True


class TestCleanCommandExtended:
    def test_no_effective_chat_raises(self):
        from utils.chat_cleaner import clean_command

        ctx = _ctx()
        update = MagicMock()
        update.message = MagicMock()
        update.message.message_id = 99
        update.effective_chat = None
        with pytest.raises(AttributeError):
            _run(clean_command(update, ctx))


class TestSafeEditOrSendBenignMessages:
    def test_benign_exact_same(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Bad Request: message is exactly the same as before")
        )
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert isinstance(result, Message)

    def test_benign_not_found(self):
        from utils.chat_cleaner import safe_edit_or_send

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message to edit not found")
        )
        result = _run(safe_edit_or_send(query, ctx, "text"))
        assert isinstance(result, Message)


class TestSafeEditPlainBenignMessages:
    def test_benign_exact_same(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("message is exactly the same")
        )
        result = _run(safe_edit_plain(query, ctx, "text"))
        assert result is None

    def test_benign_not_found(self):
        from utils.chat_cleaner import safe_edit_plain

        ctx = _ctx()
        query = _callback_query()
        query.edit_message_text = AsyncMock(
            side_effect=Exception("Message to edit not found")
        )
        result = _run(safe_edit_plain(query, ctx, "text"))
        assert result is None


class TestSendStepExtended:
    def test_truncates_text(self):
        from utils.chat_cleaner import MAX_MESSAGE_LENGTH, send_step

        ctx = _ctx()
        update = _update()
        long = "X" * (MAX_MESSAGE_LENGTH + 300)
        _run(send_step(update, ctx, long))
        call_kwargs = ctx.bot.send_message.call_args.kwargs
        assert len(call_kwargs["text"]) <= MAX_MESSAGE_LENGTH

    def test_returns_message(self):
        from utils.chat_cleaner import send_step

        ctx = _ctx()
        update = _update()
        result = _run(send_step(update, ctx, "step"))
        assert isinstance(result, Message)
        assert ctx.user_data["last_msg"] == 200

    def test_no_previous_step_no_delete(self):
        from utils.chat_cleaner import send_step

        ctx = _ctx()
        update = _update()
        _run(send_step(update, ctx, "step"))
        delete_calls = ctx.bot.delete_message.await_call_list
        for c in delete_calls:
            assert c.kwargs.get("message_id") != 99


class TestReplyFinalExtended:
    def test_returns_message(self):
        from utils.chat_cleaner import reply_final

        ctx = _ctx()
        update = _update()
        result = _run(reply_final(update, ctx, "done"))
        assert isinstance(result, Message)

    def test_does_not_set_last_msg(self):
        from utils.chat_cleaner import reply_final

        ctx = _ctx()
        update = _update()
        _run(reply_final(update, ctx, "done"))
        assert "last_msg" not in ctx.user_data


class TestScheduleDeleteExtended:
    def test_default_delay(self):
        from utils.chat_cleaner import DELETE_DELAY, schedule_delete

        ctx = _ctx()
        _run(schedule_delete(ctx, 1, 42))
        call_kwargs = ctx.job_queue.run_once.call_args.kwargs
        assert call_kwargs["when"] == DELETE_DELAY

    def test_job_data_contains_ids(self):
        from utils.chat_cleaner import schedule_delete

        ctx = _ctx()
        _run(schedule_delete(ctx, 99, 88, delay=5))
        call_kwargs = ctx.job_queue.run_once.call_args.kwargs
        assert call_kwargs["data"]["chat_id"] == 99
        assert call_kwargs["data"]["message_id"] == 88

    def test_multiple_existing_jobs_cancelled(self):
        from utils.chat_cleaner import schedule_delete

        j1 = MagicMock()
        j2 = MagicMock()
        ctx = _ctx(
            job_queue=MagicMock(
                get_jobs_by_name=MagicMock(return_value=[j1, j2]),
                run_once=MagicMock(),
            )
        )
        _run(schedule_delete(ctx, 1, 100))
        j1.schedule_removal.assert_called_once()
        j2.schedule_removal.assert_called_once()

    def test_schedule_delete_message_id_zero_skipped(self):
        from utils.chat_cleaner import schedule_delete

        ctx = _ctx()
        _run(schedule_delete(ctx, 1, 0))
        ctx.job_queue.run_once.assert_not_called()


class TestConstants:
    def test_delete_delay_value(self):
        from utils.chat_cleaner import DELETE_DELAY

        assert DELETE_DELAY == 120

    def test_max_tracked_msgs_value(self):
        from utils.chat_cleaner import MAX_TRACKED_MSGS

        assert MAX_TRACKED_MSGS == 200

    def test_max_message_length_value(self):
        from utils.chat_cleaner import MAX_MESSAGE_LENGTH

        assert MAX_MESSAGE_LENGTH == 4090

    def test_truncation_suffix_content(self):
        from utils.chat_cleaner import MESSAGE_TRUNCATION_SUFFIX

        assert "تم اقتطاع" in MESSAGE_TRUNCATION_SUFFIX

    def test_chat_msgs_ttl_seconds(self):
        from utils.chat_cleaner import CHAT_MSGS_TTL_SECONDS

        assert CHAT_MSGS_TTL_SECONDS == 7200

    def test_delete_messages_chunk(self):
        from utils.chat_cleaner import DELETE_MESSAGES_CHUNK

        assert DELETE_MESSAGES_CHUNK == 100

    def test_protected_chat_types(self):
        from utils.chat_cleaner import _PROTECTED_CHAT_TYPES  # type: ignore[reportPrivateUsage]

        assert "channel" in _PROTECTED_CHAT_TYPES
        assert "group" not in _PROTECTED_CHAT_TYPES
        assert "supergroup" not in _PROTECTED_CHAT_TYPES
        assert "private" not in _PROTECTED_CHAT_TYPES

    def test_benign_edit_errors(self):
        from utils.chat_cleaner import _BENIGN_EDIT_ERRORS  # type: ignore[reportPrivateUsage]

        assert len(_BENIGN_EDIT_ERRORS) >= 3
        assert "Message is not modified" in _BENIGN_EDIT_ERRORS
        assert "Message to edit not found" in _BENIGN_EDIT_ERRORS
        assert "exactly the same" in _BENIGN_EDIT_ERRORS
        assert "no text in the message" in _BENIGN_EDIT_ERRORS
