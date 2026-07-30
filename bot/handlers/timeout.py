import logging
import sqlite3

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.messages import (
    CANCELLED,
    TIMEOUT_CANCEL_BTN,
    TIMEOUT_HEADER,
    TIMEOUT_MINS_5,
    TIMEOUT_MINS_15,
    TIMEOUT_MINS_30,
    TIMEOUT_MINS_60,
    TIMEOUT_NO_LIMIT,
    TIMEOUT_SAVE_ERROR,
    TIMEOUT_SAVED,
    TIMEOUT_SAVED_MINS,
    TIMEOUT_SAVED_NO_LIMIT,
)
from database.repositories.user_sessions import set_session_timeout
from utils.admin_decorator import admin_only
from utils.callback_utils import safe_answer_callback

logger = logging.getLogger(__name__)

TIMEOUT_OPTIONS = [
    (TIMEOUT_MINS_5, 5),
    (TIMEOUT_MINS_15, 15),
    (TIMEOUT_MINS_30, 30),
    (TIMEOUT_MINS_60, 60),
    (TIMEOUT_NO_LIMIT, 0),
]


@admin_only
async def cmd_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /timeout command to configure session timeout."""
    keyboard = []
    for label, value in TIMEOUT_OPTIONS:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"set_timeout:{value}")])

    keyboard.append([InlineKeyboardButton(TIMEOUT_CANCEL_BTN, callback_data="cancel_timeout")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = TIMEOUT_HEADER

    if update.message:
        await update.message.reply_html(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )


@admin_only
async def handle_timeout_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback from timeout selection."""
    query = update.callback_query
    await safe_answer_callback(query)

    data = query.data
    if data == "cancel_timeout":
        await query.edit_message_text(CANCELLED)
        return

    try:
        val = int(data.split(":")[1])
        set_session_timeout(query.from_user.id, val)

        msg = TIMEOUT_SAVED
        if val == 0:
            msg += TIMEOUT_SAVED_NO_LIMIT
        else:
            msg += TIMEOUT_SAVED_MINS.format(val=val)

        await query.edit_message_text(msg)
    except (ValueError, sqlite3.Error) as e:
        logger.error("Error setting timeout: %s", e)
        await query.edit_message_text(TIMEOUT_SAVE_ERROR)
