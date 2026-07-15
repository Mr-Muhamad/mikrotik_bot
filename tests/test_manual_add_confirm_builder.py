"""Regression tests for the manual router-add flow.

Guards against the name-collision bug where the handler function
`manual_add_confirm(update, context)` shadowed the callback-data builder
`manual_add_confirm(yes)` imported from callback_constants, causing
`_confirm_keyboard()` to call the handler and crash the confirm step.
"""

import inspect

from bot.handlers.router_flows import manual_add
from bot.handlers.callback_constants import manual_add_confirm as build_manual_add_confirm


def test_confirm_keyboard_uses_builder_not_handler():
    kb = manual_add._confirm_keyboard()
    buttons = kb.inline_keyboard[0]
    assert [b.callback_data for b in buttons] == [
        build_manual_add_confirm(True),
        build_manual_add_confirm(False),
    ]
    assert build_manual_add_confirm(True) == "confirm_manual_add_yes"
    assert build_manual_add_confirm(False) == "confirm_manual_add_no"


def test_manual_add_confirm_is_the_handler_not_the_builder():
    # The handler must remain a coroutine with (update, context) signature.
    assert inspect.iscoroutinefunction(manual_add.manual_add_confirm)
    params = list(inspect.signature(manual_add.manual_add_confirm).parameters)
    assert params == ["update", "context"]


def test_manual_add_confirm_handler_matches_pattern():
    # Simulate the ConversationHandler callback routing used in registrations.
    from bot.handlers.callback_constants import PATTERNS

    import re

    pattern = re.compile(PATTERNS["confirm_manual_add"])
    assert pattern.match(build_manual_add_confirm(True))
    assert pattern.match(build_manual_add_confirm(False))
    assert not pattern.match("confirm_manual_add_maybe")

