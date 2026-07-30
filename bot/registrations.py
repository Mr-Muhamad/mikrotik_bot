"""Centralised handler registration catalog.

Imports every handler function and registers it with the handler_registry.
main.py then reads the registry to build the application.

This module is now a thin wiring layer (Step 3b of the SRP refactor). The
actual registration calls live in ``bot/registration_parts``:

* ``bot.registration_parts.standalone`` — standalone (non-conversation)
  handlers (CommandHandlers + CallbackQueryHandlers). Imported FIRST so
  standalone decorators execute before conversation decorators.
* ``bot.registration_parts.conversation`` — entry_points / states /
  fallbacks for the main ConversationHandler. Imported AFTER standalone.
* ``bot.registration_parts.separate_handlers`` — builders for the two
  short separate ConversationHandlers (rename, manual_add) that must be
  registered before standalone handlers.

Registration order contract (protected by ``test_registration_order.py``):

1. Import ``standalone`` (populates standalone handlers in the registry).
2. Import ``conversation`` (populates main CH entry_points/states/fallbacks
   in the registry; standalone decorators already ran first).
3. ``build_all(application)``:
   a. ``register_separate_conversation_handlers(application)`` — adds
      rename/manual_add CHs to the application FIRST.
   b. ``build_application(application, constants)`` — builds the main CH
      from the registry and adds it plus all standalone handlers LAST.

This preserves the exact ordering guarantees the tests assert:
separate CHs precede the standalone ``cancel``; main CH is added after
all standalone handlers.
"""

from telegram.ext import Application

import bot.handlers.constants as constants  # noqa: F401 — passed to build_application
import bot.registration_parts.standalone  # noqa: F401 — side-effect import populates standalone registry  # pyright: ignore[reportUnusedImport]
import bot.registration_parts.conversation  # noqa: F401 — side-effect import populates CH registry  # pyright: ignore[reportUnusedImport]
from bot.registration_parts.separate_handlers import (  # noqa: E501
    register_separate_conversation_handlers,
)
from utils.handler_registry import build_application


def build_all(application: Application) -> None:  # type: ignore[reportMissingTypeArgument]
    """Build all handlers from registry and add to application.

    Registration order is critical:

    1. **Separate ConversationHandlers** (rename, manual_add) — registered
       FIRST so their ``/cancel`` and ``/start`` fallbacks take precedence
       while a conversation is active. Otherwise the standalone ``cancel``
       CommandHandler preempts them and the conversation state stays STUCK.

    2. **Main ConversationHandler + standalone handlers** — registered LAST
       via ``build_application`` so the separate CHs above win while active,
       and the main CH keeps priority over standalone for its own fallback
       commands.
    """
    register_separate_conversation_handlers(application)
    build_application(application, constants)
