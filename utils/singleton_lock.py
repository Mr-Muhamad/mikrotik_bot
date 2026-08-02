"""Single-instance enforcement using file-based locks.

Prevents two `python main.py` processes from running simultaneously,
which would cause a `Conflict: terminated by other getUpdates request`
error from the Telegram Bot API.

Usage:
    from utils.singleton_lock import acquire_lock, release_lock

    if not acquire_lock():
        sys.exit("Bot is already running")

Platform support:
    - Windows: msvcrt.locking on a writable file
    - POSIX (Linux/macOS): fcntl.flock on a lock file
"""

import logging
import os
import sys
import tempfile
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_LOCK_FILENAME = "mikrotik_bot.lock"
_lock_handle = None


def _get_lock_path() -> str:
    """Return the path to the lock file, in the system temp dir."""
    return os.path.join(tempfile.gettempdir(), _LOCK_FILENAME)


def acquire_lock(force: bool = False) -> bool:
    """Try to acquire a single-instance lock.

    Args:
        force: If True, bypass the lock check (for tests / debugging).

    Returns:
        True if lock acquired (we're the only instance).
        False if another instance already holds the lock.
    """
    global _lock_handle
    if force:
        logger.warning("Single-instance lock BYPASSED via force=True")
        return True

    lock_path = _get_lock_path()
    try:
        if sys.platform == "win32":
            import msvcrt

            _lock_handle = open(lock_path, "w+")
            try:
                msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                _lock_handle.close()
                _lock_handle = None
                return False
        else:
            import fcntl

            _lock_handle = open(lock_path, "w+")
            try:
                fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                _lock_handle.close()
                _lock_handle = None
                return False

        # Write PID for diagnostics
        _lock_handle.write(str(os.getpid()))
        _lock_handle.flush()
        logger.info("Acquired single-instance lock: %s (pid=%d)", lock_path, os.getpid())
        return True
    except OSError as e:
        logger.error("Failed to acquire lock: %s", e)
        return False


def release_lock() -> None:
    """Release the single-instance lock if held. Safe to call multiple times."""
    global _lock_handle
    if _lock_handle is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                logger.debug("Failed to unlock (msvcrt) single-instance lock")
        else:
            import fcntl

            try:
                fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                logger.debug("Failed to unlock (fcntl) single-instance lock")
        _lock_handle.close()
        logger.info("Released single-instance lock")
    except OSError as e:
        logger.warning("Error releasing lock: %s", e)
    finally:
        _lock_handle = None


@contextmanager
def single_instance(force: bool = False):
    """Context manager that enforces single-instance execution.

    Example:
        with single_instance():
            application.run_polling()
    """
    if not acquire_lock(force=force):
        sys.exit("❌ Another instance of the bot is already running. Exiting.")
    try:
        yield
    finally:
        release_lock()
