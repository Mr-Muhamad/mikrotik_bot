"""Decorator-based handler registry for python-telegram-bot.

Supports both single-CH (legacy) and multi-CH (grouped) registration.

Example (single CH — legacy):
    from utils.handler_registry import entry_point, state, fallback, standalone

    @standalone(CommandHandler, command="start")
    async def start(update, context): ...

    @entry_point(CallbackQueryHandler, pattern="^hotspot_add$")
    async def hotspot_add_start(update, context): ...

    @state("WAITING_USERNAME").message(filters.TEXT & ~filters.COMMAND)
    async def hotspot_add_username(update, context): ...

Example (multi-CH — grouped):
    from utils.handler_registry import group

    add_group = group("hotspot_add")

    @add_group.entry_point(CallbackQueryHandler, pattern="^hotspot_add$")
    async def hotspot_add_start(update, context): ...

    @add_group.state("WAITING_USERNAME").message(filters.TEXT)
    async def hotspot_add_username(update, context): ...
"""

from collections import defaultdict
from typing import Any, TypedDict

from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
)

from utils.request_id import bind_request_id_from_update


class _RegistryEntry(TypedDict):
    cls: type[Any]
    func: Any
    kwargs: dict[str, Any]


class _GroupData(TypedDict):
    entry_points: list[_RegistryEntry]
    states: dict[str, list[_RegistryEntry]]
    fallbacks: list[_RegistryEntry]


def _load_guard():
    """Lazily import the navigation-guard functions (avoids import cycles)."""
    from bot.router_selector import navigation_guard, requires_router_check

    return navigation_guard, requires_router_check


_registry: dict[str, Any] = {
    "entry_points": [],
    "states": defaultdict(list),
    "fallbacks": [],
    "standalone": [],
    "error_handler": None,
    "groups": {},
}


class _GroupBuilder:
    """Builder for a named ConversationHandler group."""

    def __init__(self, name: str):
        self.name = name
        if name not in _registry["groups"]:
            _registry["groups"][name] = _GroupData(
                entry_points=[],
                states=defaultdict(list),
                fallbacks=[],
            )

    def entry_point(self, handler_cls: type[Any], **kwargs: Any) -> Any:
        """Register an entry point for this group's CH."""

        def decorator(func: Any) -> Any:
            _registry["groups"][self.name]["entry_points"].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def fallback(self, handler_cls: type[Any], **kwargs: Any) -> Any:
        """Register a fallback for this group's CH."""

        def decorator(func: Any) -> Any:
            _registry["groups"][self.name]["fallbacks"].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def state(self, state_name: str) -> Any:
        """Start building a state for this group's CH."""
        return _GroupStateBuilder(self.name, state_name)


class _GroupStateBuilder:
    def __init__(self, group_name: str, state_name: str) -> None:
        self._group_name = group_name
        self._state_name = state_name

    def _add(self, handler_cls: type[Any], **kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            _registry["groups"][self._group_name]["states"][self._state_name].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def callback(self, pattern: str) -> Any:
        """Register a CallbackQueryHandler for this state."""
        return self._add(CallbackQueryHandler, pattern=pattern)

    def message(self, filter_obj: Any) -> Any:
        """Register a MessageHandler for this state."""
        return self._add(MessageHandler, filters=filter_obj)

    def command(self, command_str: str) -> Any:
        """Register a CommandHandler for this state."""
        return self._add(CommandHandler, command=command_str)


def group(name: str) -> _GroupBuilder:
    """Create or retrieve a named group for a separate ConversationHandler.

    Usage:
        add_group = group("hotspot_add")

        @add_group.entry_point(CallbackQueryHandler, pattern="^hotspot_add$")
        async def hotspot_add_start(update, context): ...
    """
    return _GroupBuilder(name)


def _register(target: str, handler_cls: type[Any], **kwargs: Any) -> Any:
    def decorator(func: Any) -> Any:
        _registry[target].append(
            _RegistryEntry(
                cls=handler_cls,
                func=func,
                kwargs=kwargs,
            )
        )
        return func

    return decorator


def entry_point(handler_cls: type[Any], **kwargs: Any) -> Any:
    """Register a ConversationHandler entry point (main CH)."""
    return _register("entry_points", handler_cls, **kwargs)


def fallback(handler_cls: type[Any], **kwargs: Any) -> Any:
    """Register a ConversationHandler fallback (main CH)."""
    return _register("fallbacks", handler_cls, **kwargs)


def standalone(handler_cls: type[Any], **kwargs: Any) -> Any:
    """Register a standalone (non-ConversationHandler) handler."""
    return _register("standalone", handler_cls, **kwargs)


def error_handler(func: Any) -> Any:
    """Register the global error handler."""
    _registry["error_handler"] = func
    return func


class _StateBuilder:
    def __init__(self, state_name: str) -> None:
        self._state_name = state_name

    def _add(self, handler_cls: type[Any], **kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            _registry["states"][self._state_name].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def callback(self, pattern: str) -> Any:
        """Register a CallbackQueryHandler for this state."""
        return self._add(CallbackQueryHandler, pattern=pattern)

    def message(self, filter_obj: Any) -> Any:
        """Register a MessageHandler for this state."""
        return self._add(MessageHandler, filters=filter_obj)

    def command(self, command_str: str) -> Any:
        """Register a CommandHandler for this state."""
        return self._add(CommandHandler, command=command_str)


def state(state_name: str) -> _StateBuilder:
    """Start building a state handler registration.

    Usage:
        @state("WAITING_USERNAME").message(filters.TEXT & ~filters.COMMAND)
        async def handler(update, context): ...
    """
    return _StateBuilder(state_name)


def _build_handler(entry: _RegistryEntry) -> Any:
    func = entry["func"]
    command = entry["kwargs"].get("command")
    pattern = entry["kwargs"].get("pattern")
    navigation_guard, requires_router_check = _load_guard()
    if requires_router_check(command, pattern, func):
        func = navigation_guard(func)
    wrapped = bind_request_id_from_update(func)
    return entry["cls"](callback=wrapped, **entry["kwargs"])


def build_application(application: Any, constants_module: Any) -> None:
    """Build all handlers from the registry and add them to the application.

    Creates:
    1. Main ConversationHandler (legacy single-CH handlers)
    2. Separate CHs for each registered group
    3. Standalone handlers
    4. Global error handler

    Args:
        application: telegram.ext.Application instance.
        constants_module: The module containing WAITING_* state constants
                         (typically bot.handlers or bot.handlers.constants).
    """

    # 0. Standalone handlers (added FIRST so commands like /help, /metrics,
    #    /logs are handled directly and are not swallowed by any
    #    ConversationHandler's fallbacks at state=None).
    for h in _registry["standalone"]:
        application.add_handler(_build_handler(h))

    # 1. Build main ConversationHandler (legacy)
    states: dict[Any, list[Any]] = {}
    for state_name, handlers in _registry["states"].items():
        state_value = getattr(constants_module, state_name)
        states[state_value] = [_build_handler(h) for h in handlers]

    main_conv = ConversationHandler(
        entry_points=[_build_handler(h) for h in _registry["entry_points"]],
        states=states,
        fallbacks=[_build_handler(h) for h in _registry["fallbacks"]],
        per_message=False,
        conversation_timeout=300,  # 5 minutes timeout to prevent hanging sessions
    )

    # 2. Build grouped ConversationHandlers
    for group_name, group_data in _registry["groups"].items():
        if not group_data["entry_points"]:
            continue  # Skip empty groups

        group_states: dict[Any, list[Any]] = {}
        for state_name, handlers in group_data["states"].items():
            state_value = getattr(constants_module, state_name)
            group_states[state_value] = [_build_handler(h) for h in handlers]

        group_conv = ConversationHandler(
            entry_points=[_build_handler(h) for h in group_data["entry_points"]],
            states=group_states,
            fallbacks=[_build_handler(h) for h in group_data["fallbacks"]],
            per_message=False,
            name=group_name,
            conversation_timeout=300,  # 5 minutes timeout
        )
        # Add group CH after standalone handlers so their fallbacks
        # (cancel/start/go_back) take precedence while a conversation is
        # active, without swallowing non-conversation commands.
        application.add_handler(group_conv)

    # 3. Main CH (added last)
    application.add_handler(main_conv)

    # 5. Error handler
    if _registry["error_handler"]:
        wrapped_error_handler = bind_request_id_from_update(_registry["error_handler"])
        application.add_error_handler(wrapped_error_handler)
