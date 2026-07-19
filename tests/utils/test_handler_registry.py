"""Tests for the handler registry decorator API and build_application."""

from collections import defaultdict
from unittest.mock import MagicMock

import pytest
from telegram.ext import (
    CommandHandler,
    filters,
)

from utils import handler_registry as reg


@pytest.fixture(autouse=True)
def _reset_registry():
    saved = {k: list(v) if isinstance(v, list) else v for k, v in reg._registry.items()}
    saved["states"] = {k: list(v) for k, v in reg._registry["states"].items()}
    reg._registry["entry_points"] = []
    reg._registry["states"] = defaultdict(list)
    reg._registry["fallbacks"] = []
    reg._registry["standalone"] = []
    reg._registry["error_handler"] = None
    yield
    reg._registry["entry_points"] = saved["entry_points"]
    reg._registry["states"] = saved["states"]
    reg._registry["fallbacks"] = saved["fallbacks"]
    reg._registry["standalone"] = saved["standalone"]
    reg._registry["error_handler"] = saved["error_handler"]


class TestDecoratorRegistration:
    def test_entry_point_decorator(self):
        @reg.entry_point(CommandHandler, command="start")
        async def handler(update, context):
            pass

        assert len(reg._registry["entry_points"]) == 1
        assert reg._registry["entry_points"][0]["func"] is handler

    def test_fallback_decorator(self):
        @reg.fallback(CommandHandler, command="cancel")
        async def handler(update, context):
            pass

        assert len(reg._registry["fallbacks"]) == 1

    def test_standalone_decorator(self):
        @reg.standalone(CommandHandler, command="help")
        async def handler(update, context):
            pass

        assert len(reg._registry["standalone"]) == 1

    def test_error_handler_decorator(self):
        @reg.error_handler
        async def handler(update, context):
            pass

        assert reg._registry["error_handler"] is handler

    def test_state_callback_decorator(self):
        @reg.state("WAITING_X").callback("^x$")
        async def handler(update, context):
            pass

        assert "WAITING_X" in reg._registry["states"]
        assert len(reg._registry["states"]["WAITING_X"]) == 1

    def test_state_message_decorator(self):
        @reg.state("WAITING_Y").message(filters.TEXT)
        async def handler(update, context):
            pass

        assert len(reg._registry["states"]["WAITING_Y"]) == 1

    def test_state_command_decorator(self):
        @reg.state("WAITING_Z").command("cancel")
        async def handler(update, context):
            pass

        assert len(reg._registry["states"]["WAITING_Z"]) == 1

    def test_decorator_returns_original_function(self):
        async def my_func():
            return 1

        wrapped = reg.standalone(CommandHandler, command="x")(my_func)
        assert wrapped is my_func


class TestBuildApplication:
    def test_build_application_creates_conversation(self):
        @reg.entry_point(CommandHandler, command="add")
        async def ep(update, context):
            pass

        @reg.state("WAIT").message(filters.TEXT)
        async def st(update, context):
            pass

        @reg.fallback(CommandHandler, command="cancel")
        async def fb(update, context):
            pass

        @reg.standalone(CommandHandler, command="help")
        async def sa(update, context):
            pass

        @reg.error_handler
        async def eh(update, context):
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
        async def func(update, context):
            pass

        entry = {
            "cls": CommandHandler,
            "func": func,
            "kwargs": {"command": "x"},
        }
        h = reg._build_handler(entry)
        assert isinstance(h, CommandHandler)
