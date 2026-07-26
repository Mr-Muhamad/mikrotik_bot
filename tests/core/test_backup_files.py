"""Tests for core.backup.files — file path utilities."""

import os
import tempfile
from datetime import UTC, datetime

import pytest

from core.backup.files import (
    BACKUP_FILE_EXTENSIONS,
    cleanup_old_backups,
    cleanup_old_files,
    get_ftp_port,
    is_safe_filename,
    is_valid_router_backup_name,
    parse_router_creation_time,
    resolve_local_backup_file,
    safe_join_file,
    sanitize_router_name,
)


class TestGetFtpPort:
    def test_returns_21(self):
        assert get_ftp_port() == 21

    def test_ignores_argument(self):
        assert get_ftp_port("any_key") == 21


class TestParseRouterCreationTime:
    def test_valid_format(self):
        dt = parse_router_creation_time("Jul/20/2026 14:30:00")
        assert dt.year == 2026
        assert dt.month == 7
        assert dt.tzinfo == UTC

    def test_iso_format(self):
        dt = parse_router_creation_time("2026-07-20 14:30:00")
        assert dt.year == 2026

    def test_none_returns_min(self):
        dt = parse_router_creation_time(None)
        assert dt == datetime.min.replace(tzinfo=UTC)

    def test_empty_string_returns_min(self):
        dt = parse_router_creation_time("")
        assert dt == datetime.min.replace(tzinfo=UTC)

    def test_garbage_returns_min(self):
        dt = parse_router_creation_time("not-a-date")
        assert dt == datetime.min.replace(tzinfo=UTC)


class TestSanitizeRouterName:
    def test_alphanumeric(self):
        assert sanitize_router_name("Router1") == "Router1"

    def test_special_chars(self):
        assert sanitize_router_name("Router 1!") == "Router_1"

    def test_empty_becomes_router(self):
        assert sanitize_router_name("") == "router"

    def test_all_special_becomes_router(self):
        assert sanitize_router_name("!@#$%") == "router"

    def test_preserves_dot_dash_underscore(self):
        assert sanitize_router_name("a-b_c.d") == "a-b_c.d"


class TestIsSafeFilename:
    def test_valid(self):
        assert is_safe_filename("backup.backup")

    def test_empty(self):
        assert not is_safe_filename("")

    def test_null_byte(self):
        assert not is_safe_filename("backup\x00.backup")

    def test_double_dot(self):
        assert not is_safe_filename("../backup")

    def test_slash(self):
        assert not is_safe_filename("dir/backup")

    def test_backslash(self):
        assert not is_safe_filename("dir\\backup")

    def test_basename_mismatch(self):
        assert not is_safe_filename("/abs/path/backup")


class TestSafeJoinFile:
    def test_valid_join(self):
        result = safe_join_file("/tmp", "test.backup", BACKUP_FILE_EXTENSIONS)
        assert result.endswith("test.backup")

    def test_rejects_unsafe(self):
        with pytest.raises(ValueError):
            safe_join_file("/tmp", "../etc/passwd", BACKUP_FILE_EXTENSIONS)

    def test_rejects_wrong_extension(self):
        with pytest.raises(ValueError):
            safe_join_file("/tmp", "test.exe", BACKUP_FILE_EXTENSIONS)


class TestResolveLocalBackupFile:
    def test_valid(self):
        result = resolve_local_backup_file("/tmp", "backup_test.backup")
        assert result.endswith("backup_test.backup")

    def test_invalid(self):
        with pytest.raises(ValueError):
            resolve_local_backup_file("/tmp", "test.exe")


class TestIsValidRouterBackupName:
    def test_backup(self):
        assert is_valid_router_backup_name("backup_2026.backup")

    def test_export(self):
        assert is_valid_router_backup_name("export_2026.rsc")

    def test_invalid(self):
        assert not is_valid_router_backup_name("test.exe")

    def test_path_traversal(self):
        assert not is_valid_router_backup_name("../backup.backup")

    def test_empty(self):
        assert not is_valid_router_backup_name("")


class TestCleanupOldBackups:
    def test_removes_old_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                d = os.path.join(tmpdir, f"router1_{i}")
                os.makedirs(d)
            deleted = cleanup_old_backups(tmpdir, "router1", keep=2)
            assert deleted == 3
            remaining = [e for e in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, e))]
            assert len(remaining) == 2

    def test_noop_when_within_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(2):
                os.makedirs(os.path.join(tmpdir, f"router1_{i}"))
            deleted = cleanup_old_backups(tmpdir, "router1", keep=5)
            assert deleted == 0

    def test_nonexistent_dir(self):
        deleted = cleanup_old_backups("/nonexistent/path", "router1")
        assert deleted == 0


class TestCleanupOldFiles:
    def test_removes_old_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(4):
                path = os.path.join(tmpdir, f"prefix_{i}.tar")
                with open(path, "w") as f:
                    f.write("x")
            deleted = cleanup_old_files(tmpdir, "prefix_", keep=1)
            assert deleted == 3

    def test_nonexistent_dir(self):
        deleted = cleanup_old_files("/nonexistent", "prefix_")
        assert deleted == 0
