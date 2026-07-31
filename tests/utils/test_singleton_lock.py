"""Tests for utils.singleton_lock — single-instance enforcement."""

import os
import sys
import tempfile

import pytest

from utils import singleton_lock
from utils.singleton_lock import (
    _get_lock_path,
    acquire_lock,
    release_lock,
    single_instance,
)


@pytest.fixture(autouse=True)
def _reset_lock():
    """Ensure lock is released after each test."""
    yield
    release_lock()


# ─── acquire_lock tests ───────────────────────────────────────


class TestAcquireLock:
    def test_force_mode_returns_true(self):
        assert acquire_lock(force=True) is True
        release_lock()

    def test_acquire_and_release(self, monkeypatch):
        # Use a unique lock path for isolation
        test_path = os.path.join(tempfile.gettempdir(), "test_mikrotik_bot.lock")
        monkeypatch.setattr(singleton_lock, "_get_lock_path", lambda: test_path)
        assert acquire_lock() is True
        release_lock()

    def test_second_acquire_fails(self, monkeypatch):
        test_path = os.path.join(tempfile.gettempdir(), "test_double_lock.lock")
        monkeypatch.setattr(singleton_lock, "_get_lock_path", lambda: test_path)
        # First instance acquires
        assert acquire_lock() is True
        # Second instance cannot acquire (handle still held)
        # We need to simulate a separate process: try from a different file descriptor
        second_handle = open(test_path, "r+")
        if sys.platform == "win32":
            import msvcrt

            with pytest.raises(OSError):
                msvcrt.locking(second_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            with pytest.raises(OSError):
                fcntl.flock(second_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        second_handle.close()
        release_lock()


# ─── release_lock tests ───────────────────────────────────────


class TestReleaseLock:
    def test_release_when_none_held(self):
        # Should be idempotent
        release_lock()
        release_lock()
        # No exception

    def test_release_after_acquire(self, monkeypatch):
        test_path = os.path.join(tempfile.gettempdir(), "test_release.lock")
        monkeypatch.setattr(singleton_lock, "_get_lock_path", lambda: test_path)
        acquire_lock()
        release_lock()
        # Should be able to acquire again after release
        assert acquire_lock() is True
        release_lock()


# ─── single_instance context manager tests ────────────────────


class TestSingleInstanceContext:
    def test_force_bypasses_check(self):
        with single_instance(force=True):
            pass  # No exception

    def test_second_instance_exits(self, monkeypatch):
        # Simulate an existing lock by monkey-patching acquire_lock to return False
        monkeypatch.setattr(
            "utils.singleton_lock.acquire_lock",
            lambda force=False: False,
        )
        with pytest.raises(SystemExit) as exc_info:
            with single_instance(force=False):
                pass
        assert "already running" in str(exc_info.value).lower()


# ─── _get_lock_path tests ──────────────────────────────────────


class TestGetLockPath:
    def test_returns_path_in_tempdir(self):
        path = _get_lock_path()
        assert tempfile.gettempdir() in path
        assert path.endswith("mikrotik_bot.lock")
