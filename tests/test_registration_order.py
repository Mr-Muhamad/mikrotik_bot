"""Regression guards for handler registration order and dispatch precedence.

These protect against the class of bug where a standalone handler (notably the
`cancel` CommandHandler) is registered BEFORE a ConversationHandler, so that
while a conversation is active a `/cancel` is preempted by the standalone
handler and the conversation state stays STUCK instead of ending.
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


def test_separate_conversation_handlers_precede_standalone_cancel():
    """Every top-level ConversationHandler must be registered before the
    standalone `cancel` CommandHandler, or active conversations would be
    preempted and never ended."""
    handlers = _top_level_handlers()

    ch_indices = [
        i for i, h in enumerate(handlers)
        if isinstance(h, ConversationHandler)
    ]
    assert ch_indices, "expected at least the main ConversationHandler to be registered"

    cancel_idx = None
    for i, h in enumerate(handlers):
        if isinstance(h, CommandHandler) and "cancel" in h.commands:
            cancel_idx = i
            break
    assert cancel_idx is not None, "standalone `cancel` CommandHandler must be registered"

    for idx in ch_indices:
        assert idx < cancel_idx, (
            "ConversationHandler registered after the standalone `cancel` "
            "handler would be preempted -> STUCK conversation bug regression"
        )


def test_main_conversation_handler_is_registered():
    """Sanity check that build_all wires the main ConversationHandler."""
    handlers = _top_level_handlers()
    assert any(
        isinstance(h, ConversationHandler) for h in handlers
    )
