import os
import time
from unittest.mock import patch

import pytest

from core.backup.userman import UserManagerBackupService

MODULE = "core.backup.userman"
PREFIX = "User_Manager_"


@pytest.fixture
def svc():
    return UserManagerBackupService()


# ── userman_backup ────────────────────────────────────────────────────


class TestUsermanBackup:
    @patch(f"{MODULE}.os.makedirs")
    @patch(f"{MODULE}.cleanup_old_files")
    @patch(f"{MODULE}.cleanup_router_files")
    @patch(f"{MODULE}.mikrotik_api")
    @patch(f"{MODULE}.sanitize_router_name", return_value="Router1")
    def test_userman_backup_success(
        self, _sanitize, mock_api, _cleanup_r, _cleanup_l, _makedirs, svc, tmp_path
    ):
        mock_api.get_router_name.return_value = "Router1"
        mock_api.get_userman_base_path.return_value = "/user-manager"
        with patch(f"{MODULE}.download_backup_file", return_value=(True, "http")) as mock_dl:
            result = svc.userman_backup("rk1", backup_root=str(tmp_path))

        assert result["success"] is True
        assert result["downloaded"] == [result["filename"]]
        assert "warning" not in result
        mock_api.execute_long.assert_called_once()
        mock_dl.assert_called_once()
        _cleanup_r.assert_called_once()
        _cleanup_l.assert_called_once()

    @patch(f"{MODULE}.os.makedirs")
    @patch(f"{MODULE}.cleanup_old_files")
    @patch(f"{MODULE}.cleanup_router_files")
    @patch(f"{MODULE}.mikrotik_api")
    @patch(f"{MODULE}.sanitize_router_name", return_value="R")
    def test_userman_backup_download_fails_adds_warning(
        self, _s, mock_api, _cr, _cl, _md, svc, tmp_path
    ):
        mock_api.get_router_name.return_value = "R"
        mock_api.get_userman_base_path.return_value = "/um"
        with patch(f"{MODULE}.download_backup_file", return_value=(False, "")):
            result = svc.userman_backup("rk", backup_root=str(tmp_path))

        assert result["success"] is True
        assert result["downloaded"] == []
        assert "warning" in result

    @patch(f"{MODULE}.os.makedirs")
    @patch(f"{MODULE}.cleanup_old_files")
    @patch(f"{MODULE}.cleanup_router_files")
    @patch(f"{MODULE}.mikrotik_api")
    @patch(f"{MODULE}.sanitize_router_name", return_value="R")
    def test_userman_backup_api_exception_cleans_up(
        self, _s, mock_api, _cr, _cl, _md, svc, tmp_path
    ):
        mock_api.get_router_name.return_value = "R"
        mock_api.get_userman_base_path.side_effect = Exception("api boom")

        result = svc.userman_backup("rk", backup_root=str(tmp_path))

        assert result["success"] is False
        assert "فشل" in result["message"]

    @patch(f"{MODULE}.os.makedirs")
    @patch(f"{MODULE}.cleanup_old_files")
    @patch(f"{MODULE}.cleanup_router_files")
    @patch(f"{MODULE}.mikrotik_api")
    @patch(f"{MODULE}.sanitize_router_name", return_value="R")
    def test_userman_backup_default_backup_root(self, _s, mock_api, _cr, _cl, _md, svc):
        mock_api.get_router_name.return_value = "R"
        mock_api.get_userman_base_path.return_value = "/um"
        with patch(f"{MODULE}.download_backup_file", return_value=(True, "http")):
            with patch(f"{MODULE}.backup_files") as bf:
                bf.BACKUP_DIR = "/default"
                result = svc.userman_backup("rk")

        assert result["success"] is True
        _md.assert_called_once_with(os.path.join("/default", "R", "userman"), exist_ok=True)

    @patch(f"{MODULE}.os.makedirs")
    @patch(f"{MODULE}.cleanup_old_files")
    @patch(f"{MODULE}.cleanup_router_files")
    @patch(f"{MODULE}.mikrotik_api")
    @patch(f"{MODULE}.sanitize_router_name", return_value="R")
    def test_userman_backup_cleanup_error_on_partial_file(
        self, _s, mock_api, _cr, _cl, _md, svc, tmp_path
    ):
        rdir = tmp_path / "R" / "userman"
        rdir.mkdir(parents=True)
        fake_file = rdir / f"{PREFIX}R_20260101_000000.umb"
        fake_file.write_text("partial")
        mock_api.get_router_name.return_value = "R"
        mock_api.get_userman_base_path.side_effect = Exception("boom")

        with patch(f"{MODULE}.os.path.isfile", return_value=True):
            with patch(f"{MODULE}.os.remove", side_effect=OSError("perm")):
                result = svc.userman_backup("rk", backup_root=str(tmp_path))

        assert result["success"] is False


# ── userman_restore ───────────────────────────────────────────────────


class TestUsermanRestore:
    @patch(f"{MODULE}.mikrotik_api")
    def test_userman_restore_success(self, mock_api, svc, tmp_path):
        umb = tmp_path / f"{PREFIX}R_20260101.umb"
        umb.write_text("data")
        mock_api.get_router_name.return_value = "R"
        mock_api.upload_file_to_router.return_value = True
        mock_api.get_userman_base_path.return_value = "/um"

        result = svc.userman_restore("rk", str(umb))

        assert result["success"] is True
        mock_api.upload_file_to_router.assert_called_once()
        mock_api.execute_long.assert_called_once()

    @patch(f"{MODULE}.mikrotik_api")
    def test_userman_restore_missing_file(self, mock_api, svc):
        result = svc.userman_restore("rk", "/nonexistent/file.umb")
        assert result["success"] is False
        assert "غير موجود" in result["message"]

    @patch(f"{MODULE}.mikrotik_api")
    def test_userman_restore_upload_fails(self, mock_api, svc, tmp_path):
        umb = tmp_path / f"{PREFIX}R.umb"
        umb.write_text("d")
        mock_api.get_router_name.return_value = "R"
        mock_api.upload_file_to_router.return_value = False

        result = svc.userman_restore("rk", str(umb))
        assert result["success"] is False
        assert "فشل رفع" in result["message"]
        mock_api.execute_long.assert_not_called()

    @patch(f"{MODULE}.mikrotik_api")
    def test_userman_restore_api_exception(self, mock_api, svc, tmp_path):
        umb = tmp_path / f"{PREFIX}R.umb"
        umb.write_text("d")
        mock_api.get_router_name.return_value = "R"
        mock_api.upload_file_to_router.return_value = True
        mock_api.get_userman_base_path.side_effect = Exception("load fail")

        result = svc.userman_restore("rk", str(umb))
        assert result["success"] is False
        assert "فشل الاستعادة" in result["message"]


# ── list_local_userman_backups ────────────────────────────────────────


class TestListLocalUsermanBackups:
    def test_list_no_directory(self, tmp_path):
        result = UserManagerBackupService.list_local_userman_backups(
            str(tmp_path / "missing")
        )
        assert result == []

    def test_list_with_files(self, tmp_path):
        ud = tmp_path / "userman"
        ud.mkdir()
        f1 = ud / f"{PREFIX}R1_20260101.umb"
        f1.write_text("a")
        result = UserManagerBackupService.list_local_userman_backups(str(tmp_path))
        assert len(result) == 1
        assert result[0]["filename"] == f1.name
        assert result[0]["size"] == 1

    def test_list_mixed_extensions(self, tmp_path):
        ud = tmp_path / "userman"
        ud.mkdir()
        (ud / f"{PREFIX}a.umb").write_text("x")
        (ud / f"{PREFIX}b.tar").write_text("y")
        (ud / "other.txt").write_text("z")
        (ud / f"{PREFIX}c.bad").write_text("w")
        result = UserManagerBackupService.list_local_userman_backups(str(tmp_path))
        assert len(result) == 2
        exts = {os.path.splitext(str(r["filename"]))[1] for r in result}
        assert exts == {".umb", ".tar"}

    def test_list_sorted_by_mtime(self, tmp_path):
        ud = tmp_path / "userman"
        ud.mkdir()
        f_old = ud / f"{PREFIX}old.umb"
        f_old.write_text("o")
        time.sleep(0.05)
        f_new = ud / f"{PREFIX}new.umb"
        f_new.write_text("n")
        result = UserManagerBackupService.list_local_userman_backups(str(tmp_path))
        assert result[0]["filename"] == f_new.name
        assert result[1]["filename"] == f_old.name

    def test_list_skips_dirs_and_wrong_prefix(self, tmp_path):
        ud = tmp_path / "userman"
        ud.mkdir()
        (ud / "subdir").mkdir()
        (ud / "WrongPrefix_x.umb").write_text("w")
        (ud / f"{PREFIX}ok.umb").write_text("k")
        result = UserManagerBackupService.list_local_userman_backups(str(tmp_path))
        assert len(result) == 1

    def test_list_default_backup_root(self):
        with patch(f"{MODULE}.backup_files") as bf:
            bf.BACKUP_DIR = "/default"
            with patch(f"{MODULE}.os.path.isdir", return_value=False):
                result = UserManagerBackupService.list_local_userman_backups()
        assert result == []

    def test_list_with_router_key(self, tmp_path):
        rdir = tmp_path / "MyTestRouter" / "userman"
        rdir.mkdir(parents=True)
        (rdir / f"{PREFIX}MyTestRouter_20260101.umb").write_text("x")
        (rdir / f"{PREFIX}MyTestRouter_20260102.umb").write_text("y")
        (rdir / "Other_file.txt").write_text("z")

        with patch(f"{MODULE}.mikrotik_api") as mock_api:
            mock_api.get_router_name.return_value = "MyTestRouter"
            result = UserManagerBackupService.list_local_userman_backups(
                router_key="rk_test", backup_root=str(tmp_path)
            )

        assert len(result) == 2
        assert all(f["filename"].startswith(PREFIX) for f in result)
