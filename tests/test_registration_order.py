"""Regression guards for handler registration order and dispatch precedence.

These protect against two ordering bugs:

1. The main ``ConversationHandler`` must be registered AFTER every standalone
   handler (commands like ``/help``, ``/metrics``, ``/logs`` and the navigation
   callbacks). At ``state=None`` a ConversationHandler consumes any update that
   reaches it, so if it were placed before the standalone handlers those
   commands would be silently swallowed and never answered.

2. The two *separate* ConversationHandlers (rename, manual_add) must be
   registered BEFORE the standalone ``cancel`` CommandHandler, so that while one
   of those conversations is active a ``/cancel`` is handled by the conversation
   fallback and ends cleanly instead of being preempted.
"""

from telegram.ext import Application, CommandHandler, ConversationHandler

import bot.registrations as registrations


def _top_level_handlers():
    """Return the ordered list of top-level handlers from the default group.

    In python-telegram-bot v22, ``Application.handlers`` is a dict mapping a
    group index to its ordered handler list. We inspect the default group (0).
    """
    app = Application.builder().token("123456:ABC-fake-token-for-test").build()
    registrations.build_all(app)
    handlers = app.handlers
    if isinstance(handlers, dict):
        return handlers.get(0, [])
    return list(handlers)


def test_main_conversation_handler_is_registered():
    """Sanity check that build_all wires the main ConversationHandler."""
    handlers = _top_level_handlers()
    assert any(isinstance(h, ConversationHandler) for h in handlers)


def test_main_conversation_handler_after_standalone_handlers():
    """The main ConversationHandler must be registered AFTER every standalone
    CommandHandler, otherwise its ``state=None`` catch-all would swallow
    commands such as ``/help``, ``/metrics`` and ``/logs``."""
    handlers = _top_level_handlers()

    # The main CH is the LAST registered ConversationHandler (the separate
    # rename/manual_add CHs are added first inside build_all).
    ch_indices = [
        i for i, h in enumerate(handlers) if isinstance(h, ConversationHandler)
    ]
    assert ch_indices, "expected at least the main ConversationHandler to be registered"
    main_conv_idx = ch_indices[-1]

    standalone_cmd_indices = [
        i for i, h in enumerate(handlers) if isinstance(h, CommandHandler)
    ]
    assert (
        standalone_cmd_indices
    ), "expected standalone CommandHandlers to be registered"

    for idx in standalone_cmd_indices:
        assert idx < main_conv_idx, (
            "standalone CommandHandler registered after the main "
            "ConversationHandler would be swallowed by it at state=None "
            "-> commands like /help, /metrics, /logs never answered"
        )


def test_separate_conversation_handlers_precede_standalone_cancel():
    """The two separate ConversationHandlers (rename, manual_add) must be
    registered before the standalone `cancel` CommandHandler, or an active
    conversation would be preempted and never ended (STUCK conversation)."""
    handlers = _top_level_handlers()

    ch_indices = [
        i for i, h in enumerate(handlers) if isinstance(h, ConversationHandler)
    ]
    # The main CH is the last one; the earlier ones are the separate CHs.
    separate_ch_indices = ch_indices[:-1]
    assert (
        separate_ch_indices
    ), "expected rename/manual_add ConversationHandlers to be registered"

    cancel_idx = None
    for i, h in enumerate(handlers):
        if isinstance(h, CommandHandler) and "cancel" in h.commands:
            cancel_idx = i
            break
    assert (
        cancel_idx is not None
    ), "standalone `cancel` CommandHandler must be registered"

    for idx in separate_ch_indices:
        assert idx < cancel_idx, (
            "separate ConversationHandler registered after the standalone "
            "`cancel` handler would be preempted -> STUCK conversation bug regression"
        )
