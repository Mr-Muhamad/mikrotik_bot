"""Decorator: bind a request_id from update.update_id before invoking the handler.

Usage:
    @bind_request_id_from_update
    async def my_handler(update, context):
        logger.info("doing work")  # record will carry request_id
"""

from contextlib import contextmanager
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from utils.logging_setup import bind_request_id


def bind_request_id_from_update(func):
    """Decorator that sets the request_id ContextVar to update.update_id
    for the duration of the wrapped coroutine.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
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
