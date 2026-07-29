"""Tests for core/backup/system.py — SystemBackupService and _get_backup_lock."""

import threading
from contextlib import ExitStack
from unittest.mock import patch

import pytest


class TestGetBackupLock:
    def test_returns_same_lock_for_same_key(self):
        from core.backup.system import _get_backup_lock

        lock_a = _get_backup_lock("router_X")
        lock_b = _get_backup_lock("router_X")
        assert lock_a is lock_b

    def test_returns_different_locks_for_different_keys(self):
        from core.backup.system import _get_backup_lock

        lock_a = _get_backup_lock("router_A")
        lock_b = _get_backup_lock("router_B")
        assert lock_a is not lock_b

    def test_lock_is_reentrant(self):
        from core.backup.system import _get_backup_lock

        lock = _get_backup_lock("router_RE")
        assert lock.acquire(blocking=False)
        assert lock.acquire(blocking=False)
        lock.release()
        lock.release()


class TestSystemBackupServiceFullBackup:
    P = "core.backup.system"

    @pytest.fixture(autouse=True)
    def _patches(self):
        with ExitStack() as stack:
            stack.enter_context(patch(f"{self.P}.cleanup_router_files"))
            stack.enter_context(patch(f"{self.P}.sanitize_router_name", return_value="TestRouter"))
            self.makedirs = stack.enter_context(patch(f"{self.P}.os.makedirs"))
            self.isdir = stack.enter_context(patch(f"{self.P}.os.path.isdir", return_value=False))
            self.mock_get_router_name = stack.enter_context(
                patch(f"{self.P}.mikrotik_api.get_router_name", return_value="MyRouter")
            )
            self.mock_execute_long = stack.enter_context(
                patch(f"{self.P}.mikrotik_api.execute_long", return_value=[])
            )
            self.mock_download_file = stack.enter_context(
                patch(
                    f"{self.P}.download_backup_file",
                    return_value=(True, "http"),
                )
            )
            yield

    def test_lock_contention_returns_error(self):
        from core.backup.system import SystemBackupService, _get_backup_lock

        lock = _get_backup_lock("router_LC")
        barrier = threading.Event()
        proceed = threading.Event()

        def holder():
            lock.acquire(blocking=True)
            barrier.set()
            proceed.wait(timeout=5)
            lock.release()

        t = threading.Thread(target=holder)
        t.start()
        barrier.wait(timeout=5)
        try:
            svc = SystemBackupService()
            result = svc.full_backup("router_LC")
            assert result["success"] is False
            assert "نسخ احتياطي جارية" in result["message"]
        finally:
            proceed.set()
            t.join(timeout=5)

    def test_successful_backup_downloads_both_files(self):
        from core.backup.system import SystemBackupService

        svc = SystemBackupService()
        result = svc.full_backup("key1", "backups")
        assert result["success"] is True
        assert "MyRouter" in result["message"]

    def test_successful_backup_no_downloads_warns(self):
        from core.backup.system import SystemBackupService

        self.mock_download_file.return_value = (False, "")
        svc = SystemBackupService()
        result = svc.full_backup("key2", "backups")
        assert result["success"] is True
        assert "warning" in result
        assert "فشل التحميل" in result["warning"]

    def test_exception_during_backup(self):
        from core.backup.system import SystemBackupService

        self.mock_execute_long.side_effect = RuntimeError("API timeout")
        svc = SystemBackupService()
        result = svc.full_backup("key3", "backups")
        assert result["success"] is False
        assert "فشل" in result["message"]

    def test_exception_cleanup_failure_is_tolerated(self):
        from core.backup.system import SystemBackupService

        self.mock_execute_long.side_effect = RuntimeError("boom")
        svc = SystemBackupService()
        result = svc.full_backup("key4", "backups")
        assert result["success"] is False

    def test_backup_dir_isolation_between_calls(self):
        from core.backup.system import _get_backup_lock

        lock1 = _get_backup_lock("key_a")
        lock2 = _get_backup_lock("key_b")
        assert lock1 is not lock2

    def test_default_backup_root_uses_BACKUP_DIR(self):
        from core.backup.system import SystemBackupService

        svc = SystemBackupService()
        svc.full_backup("key5")
        call_args = self.makedirs.call_args[0][0]
        assert "backups" in call_args

    def test_execute_long_called_with_correct_args(self):
        from core.backup.system import SystemBackupService

        svc = SystemBackupService()
        svc.full_backup("key_args", "backups")
        cmd_names = [c[0][1] for c in self.mock_execute_long.call_args_list]
        assert "system/backup/save" in cmd_names
        assert "export" in cmd_names

    def test_download_called_with_correct_files(self):
        from core.backup.system import SystemBackupService

        svc = SystemBackupService()
        svc.full_backup("key_dl", "backups")
        call_args = self.mock_download_file.call_args_list
        assert len(call_args) == 2
        assert call_args[0][0][1].endswith(".backup")
        assert call_args[1][0][1].endswith(".rsc")

    def test_multiple_sequential_backups_succeed(self):
        from core.backup.system import SystemBackupService

        svc = SystemBackupService()
        r1 = svc.full_backup("key_seq", "backups")
        r2 = svc.full_backup("key_seq", "backups")
        assert r1["success"] is True
        assert r2["success"] is True

    def test_lock_released_after_exception(self):
        from core.backup.system import SystemBackupService, _get_backup_lock

        self.mock_execute_long.side_effect = RuntimeError("fail")
        svc = SystemBackupService()
        svc.full_backup("key_lr", "backups")
        lock = _get_backup_lock("key_lr")
        assert lock.acquire(blocking=False)
        lock.release()
