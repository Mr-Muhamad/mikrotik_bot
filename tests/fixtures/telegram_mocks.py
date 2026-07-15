from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes, JobQueue


def make_mock_update(
    user_id: int = 724730774,
    chat_id: int = 724730774,
    text: str = "",
    callback_data: str | None = None,
) -> MagicMock:
    """Create a minimal mock Update for handler testing.

    Args:
        user_id: Telegram user ID (defaults to admin).
        chat_id: Chat ID for the conversation.
        text: Message text to simulate user input.
        callback_data: If set, simulates a callback query instead of a message.
    """
    update = MagicMock(spec=Update)(
        _user_id=user_id,
        _chat_id=chat_id,
        _text=text,
        _callback_data=callback_data,
    )

    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = user_id

    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = chat_id

    if callback_data is not None:
        update.callback_query = MagicMock()
        update.callback_query.data = callback_data
        update.callback_query.from_user.id = user_id
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.message = None
    else:
        update.callback_query = None
        update.message = MagicMock(spec=Message)
        update.message.message_id = 1
        update.message.text = text
        update.message.reply_text = AsyncMock()
        update.message.delete = AsyncMock()

    return update


def make_mock_context() -> MagicMock:
    """Create a minimal mock Context with user_data and bot_data namespaces."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {}
    context.job_queue = MagicMock(spec=JobQueue)
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.bot.delete_message = AsyncMock()
    return context


class CallbackQueryMock:
    """Minimal mock for telegram.CallbackQuery with async edit support."""

    def __init__(self, data: str = "", from_user_id: int = 724730774):
        self.data = data
        self.from_user = MagicMock()
        self.from_user.id = from_user_id
        self.message = MagicMock()
        self.message.chat_id = from_user_id
        self.edit_message_text = AsyncMock()

    async def answer(self, text=None, show_alert=False):
        pass
