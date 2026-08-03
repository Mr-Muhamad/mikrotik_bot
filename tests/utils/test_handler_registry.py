"""Tests for the handler registry decorator API and build_application."""

from collections import defaultdict
from unittest.mock import MagicMock

import pytest
from telegram.ext import (
    CommandHandler,
    filters,
)

from utils import handler_registry as reg
from utils.handler_registry import _RegistryEntry  # type: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _reset_registry():  # type: ignore[reportUnusedFunction]
    saved = {k: list(v) if isinstance(v, list) else v for k, v in reg._registry.items()}  # type: ignore[reportPrivateUsage]
    saved["states"] = {k: list(v) for k, v in reg._registry["states"].items()}  # type: ignore[reportPrivateUsage]
    reg._registry["entry_points"] = []  # type: ignore[reportPrivateUsage]
    reg._registry["states"] = defaultdict(list)  # type: ignore[reportPrivateUsage]
    reg._registry["fallbacks"] = []  # type: ignore[reportPrivateUsage]
    reg._registry["standalone"] = []  # type: ignore[reportPrivateUsage]
    reg._registry["error_handler"] = None  # type: ignore[reportPrivateUsage]
    yield
    reg._registry["entry_points"] = saved["entry_points"]  # type: ignore[reportPrivateUsage]
    reg._registry["states"] = saved["states"]  # type: ignore[reportPrivateUsage]
    reg._registry["fallbacks"] = saved["fallbacks"]  # type: ignore[reportPrivateUsage]
    reg._registry["standalone"] = saved["standalone"]  # type: ignore[reportPrivateUsage]
    reg._registry["error_handler"] = saved["error_handler"]  # type: ignore[reportPrivateUsage]


class TestDecoratorRegistration:
    def test_entry_point_decorator(self):
        @reg.entry_point(CommandHandler, command="start")
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            pass

        assert len(reg._registry["entry_points"]) == 1  # type: ignore[reportPrivateUsage]
        assert reg._registry["entry_points"][0]["func"] is handler  # type: ignore[reportPrivateUsage]

    def test_fallback_decorator(self):
        @reg.fallback(CommandHandler, command="cancel")
        async def handler(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        assert len(reg._registry["fallbacks"]) == 1  # type: ignore[reportPrivateUsage]

    def test_standalone_decorator(self):
        @reg.standalone(CommandHandler, command="help")
        async def handler(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        assert len(reg._registry["standalone"]) == 1  # type: ignore[reportPrivateUsage]

    def test_error_handler_decorator(self):
        @reg.error_handler
        async def handler(update, context):  # type: ignore[reportMissingParameterType]
            pass

        assert reg._registry["error_handler"] is handler  # type: ignore[reportPrivateUsage]

    def test_state_callback_decorator(self):
        @reg.state("WAITING_X").callback("^x$")
        async def handler(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        assert "WAITING_X" in reg._registry["states"]  # type: ignore[reportPrivateUsage]
        assert len(reg._registry["states"]["WAITING_X"]) == 1  # type: ignore[reportPrivateUsage]

    def test_state_message_decorator(self):
        @reg.state("WAITING_Y").message(filters.TEXT)
        async def handler(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        assert len(reg._registry["states"]["WAITING_Y"]) == 1  # type: ignore[reportPrivateUsage]

    def test_state_command_decorator(self):
        @reg.state("WAITING_Z").command("cancel")
        async def handler(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        assert len(reg._registry["states"]["WAITING_Z"]) == 1  # type: ignore[reportPrivateUsage]

    def test_decorator_returns_original_function(self):
        async def my_func():
            return 1

        wrapped = reg.standalone(CommandHandler, command="x")(my_func)
        assert wrapped is my_func


class TestBuildApplication:
    def test_build_application_creates_conversation(self):
        @reg.entry_point(CommandHandler, command="add")
        async def ep(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        @reg.state("WAIT").message(filters.TEXT)
        async def st(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        @reg.fallback(CommandHandler, command="cancel")
        async def fb(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        @reg.standalone(CommandHandler, command="help")
        async def sa(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        @reg.error_handler
        async def eh(update, context):  # type: ignore[reportUnusedFunction, reportMissingParameterType]
            pass

        application = MagicMock()
        constants = MagicMock()
        constants.WAIT = 42

        reg.build_application(application, constants)

        assert application.add_handler.call_count >= 2
        assert application.add_error_handler.called

    def test_build_application_without_error_handler(self):
        application = MagicMock()
        constants = MagicMock()

        reg.build_application(application, constants)
        assert not application.add_error_handler.called

    def test_build_handler_returns_ptb_handler(self):
        async def func(update, context):  # type: ignore[reportMissingParameterType]
            pass

        entry: _RegistryEntry = {
            "cls": CommandHandler,
            "func": func,
            "kwargs": {"command": "x"},
        }
        h = reg._build_handler(entry)  # type: ignore[reportPrivateUsage]
        assert isinstance(h, CommandHandler)
