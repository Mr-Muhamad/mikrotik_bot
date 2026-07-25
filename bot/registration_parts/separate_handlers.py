"""Separate (short) ConversationHandlers: rename and manual_add.

These must be registered BEFORE standalone handlers so their ``/cancel``
and ``/start`` fallbacks take precedence while the conversation is active.

Split from ``bot/registrations.py`` (Step 3b of SRP refactor). The
``_build_*_handler`` factories and ``register_separate_conversation_handlers``
live here so ``bot/registrations.py`` stays a thin wiring layer.
"""

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.ext import (
    ConversationHandler as CH,
)

import bot.handlers.constants as constants
from bot.handlers.callback_constants import PATTERNS
from bot.handlers.commands_basic import cancel, start
from bot.handlers.menus import go_back
from bot.handlers.routers import (
    manual_add_alias,
    manual_add_confirm,
    manual_add_ip,
    manual_add_pass,
    manual_add_port,
    manual_add_start,
    manual_add_user,
    rename_router_start,
    rename_router_value,
)


def _build_rename_handler() -> CH:  # type: ignore[reportMissingTypeArgument]
    """Build the separate rename ConversationHandler.

    This is a short conversation: trigger -> enter new name -> done.
    Must be registered before standalone handlers so its ``/cancel`` fallback
    takes precedence while active.
    """
    return CH(
        entry_points=[CallbackQueryHandler(rename_router_start, pattern=PATTERNS["rename_router"])],
        states={
            constants.WAITING_RENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_router_value)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )


def _build_manual_add_handler() -> CH:  # type: ignore[reportMissingTypeArgument]
    """Build the separate manual-router-add ConversationHandler.

    Multi-step: IP -> port -> user -> pass -> alias -> confirm.
    Must be registered before standalone handlers so its ``/cancel`` fallback
    takes precedence while active.
    """
    return CH(
        entry_points=[
            CallbackQueryHandler(manual_add_start, pattern=PATTERNS["manual_add_router"]),
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
                CallbackQueryHandler(manual_add_confirm, pattern=PATTERNS["confirm_manual_add"])
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )


def _build_discovery_handler() -> CH:  # type: ignore[reportMissingTypeArgument]
    """Build the separate router-discovery ConversationHandler.

    Multi-step: select discovered router -> enter username -> enter password -> done.
    Must be registered before standalone handlers so its state and /cancel take precedence.
    """
    from bot.handlers.routers import (
        disc_enter_password,
        disc_enter_username,
        discovered_router_selected,
    )

    return CH(
        entry_points=[
            CallbackQueryHandler(discovered_router_selected, pattern=PATTERNS["disc_router"]),
        ],
        states={
            constants.WAITING_DISC_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, disc_enter_username)
            ],
            constants.WAITING_DISC_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, disc_enter_password)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )


def register_separate_conversation_handlers(application: Application) -> None:  # type: ignore[reportMissingTypeArgument]
    """Register separate ConversationHandlers before standalone handlers.

    These must be registered BEFORE standalone handlers so their
    ``/cancel`` and ``/start`` fallbacks take precedence while a
    conversation is active. Otherwise the standalone ``cancel``
    CommandHandler preempts them and the conversation state stays STUCK.
    """
    application.add_handler(_build_rename_handler())
    application.add_handler(_build_manual_add_handler())
    application.add_handler(_build_discovery_handler())
