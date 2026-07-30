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

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import TypedDict

from telegram import Update
from telegram.ext import (
    Application,
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from core.metrics import record_component_result, record_telegram_request
from utils.logging_setup import (
    COMPONENT_HANDLER,
    bind_component,
    set_chat_id,
    set_user_id,
)
from utils.request_id import bind_request_id_from_update

# Type alias for async callback functions registered as handlers.
_Callback = Callable[..., Awaitable[object]]


class _RegistryEntry(TypedDict):
    cls: type[BaseHandler]  # type: ignore[type-arg]
    func: _Callback
    kwargs: dict[str, object]


class _GroupData(TypedDict):
    entry_points: list[_RegistryEntry]
    states: dict[str, list[_RegistryEntry]]
    fallbacks: list[_RegistryEntry]


class _RegistryData(TypedDict):
    entry_points: list[_RegistryEntry]
    states: dict[str, list[_RegistryEntry]]
    fallbacks: list[_RegistryEntry]
    standalone: list[_RegistryEntry]
    error_handler: _Callback | None
    groups: dict[str, _GroupData]


def _load_guard() -> tuple[Callable[..., object], Callable[..., object]]:
    """Lazily import the navigation-guard functions (avoids import cycles)."""
    from bot.router_selector import navigation_guard, requires_router_check

    return navigation_guard, requires_router_check


_registry: _RegistryData = {
    "entry_points": [],
    "states": defaultdict(list),
    "fallbacks": [],
    "standalone": [],
    "error_handler": None,
    "groups": {},
}


class _GroupBuilder:
    """Builder for a named ConversationHandler group."""

    def __init__(self, name: str) -> None:
        self.name = name
        if name not in _registry["groups"]:
            _registry["groups"][name] = _GroupData(
                entry_points=[],
                states=defaultdict(list),
                fallbacks=[],
            )

    def entry_point(
        self, handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
    ) -> Callable[[_Callback], _Callback]:
        """Register an entry point for this group's CH."""

        def decorator(func: _Callback) -> _Callback:
            _registry["groups"][self.name]["entry_points"].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def fallback(
        self, handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
    ) -> Callable[[_Callback], _Callback]:
        """Register a fallback for this group's CH."""

        def decorator(func: _Callback) -> _Callback:
            _registry["groups"][self.name]["fallbacks"].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def state(self, state_name: str) -> "_GroupStateBuilder":
        """Start building a state for this group's CH."""
        return _GroupStateBuilder(self.name, state_name)


class _GroupStateBuilder:
    def __init__(self, group_name: str, state_name: str) -> None:
        self._group_name = group_name
        self._state_name = state_name

    def _add(
        self, handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
    ) -> Callable[[_Callback], _Callback]:
        def decorator(func: _Callback) -> _Callback:
            _registry["groups"][self._group_name]["states"][self._state_name].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def callback(self, pattern: str) -> Callable[[_Callback], _Callback]:
        """Register a CallbackQueryHandler for this state."""
        return self._add(CallbackQueryHandler, pattern=pattern)

    def message(self, filter_obj: filters.BaseFilter) -> Callable[[_Callback], _Callback]:
        """Register a MessageHandler for this state."""
        return self._add(MessageHandler, filters=filter_obj)

    def command(self, command_str: str) -> Callable[[_Callback], _Callback]:
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


def _register(
    target: str,
    handler_cls: type[BaseHandler],  # type: ignore[type-arg]
    **kwargs: object,
) -> Callable[[_Callback], _Callback]:
    def decorator(func: _Callback) -> _Callback:
        _registry[target].append(
            _RegistryEntry(
                cls=handler_cls,
                func=func,
                kwargs=kwargs,
            )
        )
        return func

    return decorator


def entry_point(
    handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
) -> Callable[[_Callback], _Callback]:
    """Register a ConversationHandler entry point (main CH)."""
    return _register("entry_points", handler_cls, **kwargs)


def fallback(
    handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
) -> Callable[[_Callback], _Callback]:
    """Register a ConversationHandler fallback (main CH)."""
    return _register("fallbacks", handler_cls, **kwargs)


def standalone(
    handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
) -> Callable[[_Callback], _Callback]:
    """Register a standalone (non-ConversationHandler) handler."""
    return _register("standalone", handler_cls, **kwargs)


def error_handler(func: _Callback) -> _Callback:
    """Register the global error handler."""
    _registry["error_handler"] = func
    return func


class _StateBuilder:
    def __init__(self, state_name: str) -> None:
        self._state_name = state_name

    def _add(
        self, handler_cls: type[BaseHandler], **kwargs: object  # type: ignore[type-arg]
    ) -> Callable[[_Callback], _Callback]:
        def decorator(func: _Callback) -> _Callback:
            _registry["states"][self._state_name].append(
                _RegistryEntry(
                    cls=handler_cls,
                    func=func,
                    kwargs=kwargs,
                )
            )
            return func

        return decorator

    def callback(self, pattern: str) -> Callable[[_Callback], _Callback]:
        """Register a CallbackQueryHandler for this state."""
        return self._add(CallbackQueryHandler, pattern=pattern)

    def message(self, filter_obj: filters.BaseFilter) -> Callable[[_Callback], _Callback]:
        """Register a MessageHandler for this state."""
        return self._add(MessageHandler, filters=filter_obj)

    def command(self, command_str: str) -> Callable[[_Callback], _Callback]:
        """Register a CommandHandler for this state."""
        return self._add(CommandHandler, command=command_str)


def state(state_name: str) -> _StateBuilder:
    """Start building a state handler registration.

    Usage:
        @state("WAITING_USERNAME").message(filters.TEXT & ~filters.COMMAND)
        async def handler(update, context): ...
    """
    return _StateBuilder(state_name)


def _build_handler(entry: _RegistryEntry) -> BaseHandler:  # type: ignore[type-arg]
    func = entry["func"]
    command = entry["kwargs"].get("command")
    pattern = entry["kwargs"].get("pattern")
    navigation_guard, requires_router_check = _load_guard()
    if requires_router_check(command, pattern, func):
        func = navigation_guard(func)

    async def _wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        with bind_component(COMPONENT_HANDLER):
            if update.effective_user:
                set_user_id(update.effective_user.id)
            if update.effective_chat:
                set_chat_id(update.effective_chat.id)
            handler_name = str(getattr(func, "__name__", "unknown"))
            t0 = time.monotonic()
            try:
                result = await func(update, context)  # type: ignore[reportCallIssue]
                elapsed_ms = (time.monotonic() - t0) * 1000
                record_telegram_request(handler_name, True, elapsed_ms)
                record_component_result(COMPONENT_HANDLER, True)
                return result
            except Exception:
                elapsed_ms = (time.monotonic() - t0) * 1000
                record_telegram_request(handler_name, False, elapsed_ms)
                record_component_result(COMPONENT_HANDLER, False)
                raise

    wrapped = bind_request_id_from_update(_wrapped_handler)
    return entry["cls"](callback=wrapped, **entry["kwargs"])  # type: ignore[reportArgumentType]


def build_application(application: Application, constants_module: ModuleType) -> None:  # type: ignore[reportInvalidTypeArguments]
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
    states: dict[int, list[BaseHandler]] = {}  # type: ignore[type-arg]
    for state_name, handlers in _registry["states"].items():
        state_value = getattr(constants_module, state_name)
        states[state_value] = [_build_handler(h) for h in handlers]

    main_conv = ConversationHandler(
        entry_points=[_build_handler(h) for h in _registry["entry_points"]],
        states=states,  # type: ignore[reportArgumentType]
        fallbacks=[_build_handler(h) for h in _registry["fallbacks"]],
        per_message=False,
        conversation_timeout=300,  # 5 minutes timeout to prevent hanging sessions
    )

    # 2. Build grouped ConversationHandlers
    for group_name, group_data in _registry["groups"].items():
        if not group_data["entry_points"]:
            continue  # Skip empty groups

        group_states: dict[int, list[BaseHandler]] = {}  # type: ignore[type-arg]
        for state_name, handlers in group_data["states"].items():
            state_value = getattr(constants_module, state_name)
            group_states[state_value] = [_build_handler(h) for h in handlers]

        group_conv = ConversationHandler(
            entry_points=[_build_handler(h) for h in group_data["entry_points"]],
            states=group_states,  # type: ignore[reportArgumentType]
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

        async def _wrapped_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            with bind_component(COMPONENT_HANDLER):
                await _registry["error_handler"](update, context)  # type: ignore[reportCallIssue]

        wrapped_error_handler = bind_request_id_from_update(_wrapped_error_handler)
        application.add_error_handler(wrapped_error_handler)  # type: ignore[reportArgumentType]
