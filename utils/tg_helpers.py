"""Type-safe accessors for python-telegram-bot objects.

python-telegram-bot stubs declare many attributes as Optional (e.g.
user_data, query.data, update.message.text) for theoretical correctness,
but inside a registered handler these values are guaranteed non-None by
the framework.

Use these helpers instead of direct attribute access to satisfy
basedpyright without scattering # type: ignore across the codebase.
Each function uses assert so the guarantee is explicit and documented.
"""
from __future__ import annotations

from typing import Any

from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes


def get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    """Return context.user_data as a guaranteed non-None dict.

    user_data is always initialised by python-telegram-bot before any
    handler is called — it is safe to assert here.
    """
    assert context.user_data is not None, (
        "context.user_data is always set inside a registered handler"
    )
    return context.user_data


def get_query_data(query: CallbackQuery) -> str:
    """Return query.data as a guaranteed non-None str.

    CallbackQueryHandler only fires when data is present; the field
    is always a str inside any callback handler.
    """
    assert query.data is not None, (
        "query.data is always set inside a CallbackQueryHandler"
    )
    return query.data


def get_message_text(update: Update) -> str:
    """Return update.message.text stripped, guaranteed non-None.

    MessageHandler only fires when a text message is present.
    """
    assert update.message is not None, (
        "update.message is always set inside a MessageHandler"
    )
    assert update.message.text is not None, (
        "update.message.text is always set for text MessageHandlers"
    )
    return update.message.text.strip()


def get_message(update: Update) -> Message:
    """Return update.message as a guaranteed non-None Message.

    Use when you need the full Message object, not just its text.
    """
    assert update.message is not None, (
        "update.message is always set inside a MessageHandler"
    )
    return update.message


def get_effective_user_id(update: Update) -> int:
    """Return update.effective_user.id, guaranteed non-None.

    effective_user is always set for messages and callback queries.
    """
    assert update.effective_user is not None, (
        "update.effective_user is always set for user-originated updates"
    )
    return update.effective_user.id


def get_chat_id(update: Update) -> int:
    """Return update.effective_chat.id, guaranteed non-None."""
    assert update.effective_chat is not None, (
        "update.effective_chat is always set for user-originated updates"
    )
    return update.effective_chat.id


def get_from_user_id(query: CallbackQuery) -> int:
    """Return query.from_user.id, guaranteed non-None.

    from_user is always set on CallbackQuery objects received by the bot.
    """
    assert query.from_user is not None, (
        "query.from_user is always set on incoming CallbackQuery objects"
    )
    return query.from_user.id
