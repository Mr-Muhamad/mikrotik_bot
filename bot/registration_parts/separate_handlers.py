"""Separate (short) ConversationHandlers: rename and manual_add.

These must be registered BEFORE standalone handlers so their ``/cancel``
and ``/start`` fallbacks take precedence while the conversation is active.

Split from ``bot/registrations.py`` (Step 3b of SRP refactor). The
``_build_*_handler`` factories and ``register_separate_conversation_handlers``
live here so ``bot/registrations.py`` stays a thin wiring layer.
"""

from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler as CH,
)

from bot.handlers.callback_constants import PATTERNS
from bot.handlers.commands_basic import cancel
from bot.handlers.menus import go_back
from bot.handlers.routers import (
    rename_router_start,
    rename_router_value,
    manual_add_start,
    manual_add_ip,
    manual_add_port,
    manual_add_user,
    manual_add_pass,
    manual_add_alias,
    manual_add_confirm,
)
import bot.handlers.constants as constants


def _build_rename_handler() -> CH:
    """Build the separate rename ConversationHandler.

    This is a short conversation: trigger -> enter new name -> done.
    Must be registered before standalone handlers so its ``/cancel`` fallback
    takes precedence while active.
    """
    return CH(
        entry_points=[
            CallbackQueryHandler(rename_router_start, pattern=PATTERNS["rename_router"])
        ],
        states={
            constants.WAITING_RENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_router_value)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )


def _build_manual_add_handler() -> CH:
    """Build the separate manual-router-add ConversationHandler.

    Multi-step: IP -> port -> user -> pass -> alias -> confirm.
    Must be registered before standalone handlers so its ``/cancel`` fallback
    takes precedence while active.
    """
    return CH(
        entry_points=[
            CallbackQueryHandler(
                manual_add_start, pattern=PATTERNS["manual_add_router"]
            ),
            CommandHandler("addrouter", manual_add_start),
        ],
        states={
            constants.WAITING_MANUAL_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_ip)
            ],
            constants.WAITING_MANUAL_PORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_port)
            ],
            constants.WAITING_MANUAL_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_user)
            ],
            constants.WAITING_MANUAL_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_pass)
            ],
            constants.WAITING_MANUAL_ALIAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_alias)
            ],
            constants.WAITING_MANUAL_CONFIRM: [
                CallbackQueryHandler(
                    manual_add_confirm, pattern=PATTERNS["confirm_manual_add"]
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )


def register_separate_conversation_handlers(application) -> None:
    """Register separate ConversationHandlers before standalone handlers.

    These must be registered BEFORE standalone handlers so their
    ``/cancel`` and ``/start`` fallbacks take precedence while a
    conversation is active. Otherwise the standalone ``cancel``
    CommandHandler preempts them and the conversation state stays STUCK.
    """
    application.add_handler(_build_rename_handler())
    application.add_handler(_build_manual_add_handler())