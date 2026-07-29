"""Decorator: bind a request_id from update.update_id before invoking the handler.

Also provides trace_id support for correlating a sequence of operations
across async boundaries (handler → service → API call → response).

Usage:
    @bind_request_id_from_update
    async def my_handler(update, context):
        logger.info("doing work")  # record will carry request_id
        trace_id = new_trace_id()
        with bind_trace_id(trace_id):
            await call_downstream_service()
"""

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from utils.logging_setup import (
    bind_request_id,
    bind_trace_id,
    get_request_id,
    get_trace_id,
    new_request_id,
    new_trace_id,
)

HandlerFunc = Callable[..., Awaitable[object]]


def bind_request_id_from_update(func: HandlerFunc) -> HandlerFunc:
    """Decorator that sets the request_id ContextVar to update.update_id
    for the duration of the wrapped coroutine.
    """

    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: object,
        **kwargs: object,
    ) -> object:
        rid = str(getattr(update, "update_id", None) or "-")
        with bind_request_id(rid):
            return await func(update, context, *args, **kwargs)

    return wrapper


@contextmanager
def request_id_scope(request_id: str):
    """Context manager that sets the request_id ContextVar for the duration of the block.

    Usage:
        with request_id_scope("my-request-id"):
            logger.info("This log will carry the request_id")
    """
    with bind_request_id(request_id):
        yield


@contextmanager
def trace_id_scope(trace_id: str | None = None):
    """Context manager that sets a trace_id for the duration of the block.

    A new trace_id is auto-generated if none is provided.
    trace_id is NOT inherited from an outer scope — each call to
    trace_id_scope creates a fresh correlation boundary.

    Usage:
        with trace_id_scope():
            logger.info("All logs in this block share the same trace_id")
    """
    tid = trace_id or new_trace_id()
    with bind_trace_id(tid):
        yield