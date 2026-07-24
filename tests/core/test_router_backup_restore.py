"""Tests for core.backup.restore."""

from unittest.mock import MagicMock, patch

from core.backup.restore import BackupRestore


class TestListRouterBackups:
    def setup_method(self):
        self.restorer = BackupRestore()
        self.router_key = "discovered_1"

    @patch("core.backup.restore.mikrotik_api")
    def test_lists_system_backups(self, mock_api):
        mock_api.execute.return_value = [
            {"name": "backup_2026-07-20.backup", "size": "1024"},
            {"name": "export_2026-07-20.rsc", "size": "512"},
            {"name": "unrelated.txt", "size": "100"},
        ]
        result = self.restorer.list_router_backups(self.router_key)
        assert len(result) == 2
        types = {b["type"] for b in result}
        assert types == {"system", "export"}

    @patch("core.backup.restore.mikrotik_api")
    def test_sorted_descending(self, mock_api):
        mock_api.execute.return_value = [
            {"name": "backup_2026-07-19.backup", "size": "0"},
            {"name": "backup_2026-07-21.backup", "size": "0"},
            {"name": "backup_2026-07-20.backup", "size": "0"},
        ]
        result = self.restorer.list_router_backups(self.router_key)
        names = [b["name"] for b in result]
        assert names == sorted(names, reverse=True)

    @patch("core.backup.restore.mikrotik_api")
    def test_empty_on_exception(self, mock_api):
        mock_api.execute.side_effect = Exception("fail")
        result = self.restorer.list_router_backups(self.router_key)
        assert result == []

    @patch("core.backup.restore.mikrotik_api")
    def test_empty_list(self, mock_api):
        mock_api.execute.return_value = []
        result = self.restorer.list_router_backups(self.router_key)
        assert result == []


class TestRestoreBackup:
    def setup_method(self):
        self.restorer = BackupRestore()
        self.router_key = "discovered_1"

    @patch("core.backup.restore.mikrotik_api")
    def test_restore_system_backup(self, mock_api):
        mock_api.get_router_name.return_value = "Router1"
        result = self.restorer.restore_backup(self.router_key, "backup_2026.backup")
        assert result["success"] is True
        mock_api.execute_long.assert_called_once()

    @patch("core.backup.restore.mikrotik_api")
    def test_restore_export_backup(self, mock_api):
        mock_api.get_router_name.return_value = "Router1"
        result = self.restorer.restore_backup(self.router_key, "export_2026.rsc")
        assert result["success"] is True

    @patch("core.backup.restore.mikrotik_api")
    def test_invalid_filename_rejected(self, mock_api):
        mock_api.get_router_name.return_value = "Router1"
        result = self.restorer.restore_backup(self.router_key, "../evil.backup")
        assert result["success"] is False

    @patch("core.backup.restore.is_valid_router_backup_name", return_value=True)
    @patch("core.backup.restore.mikrotik_api")
    def test_unknown_extension(self, mock_api, _mock_validate):
        mock_api.get_router_name.return_value = "Router1"
        result = self.restorer.restore_backup(self.router_key, "backup_2026.zip")
        assert result["success"] is False

    @patch("core.backup.restore.mikrotik_api")
    def test_exception_returns_error(self, mock_api):
        mock_api.get_router_name.return_value = "Router1"
        mock_api.execute_long.side_effect = Exception("timeout")
        result = self.restorer.restore_backup(self.router_key, "backup_2026.backup")
        assert result["success"] is False
        assert "فشل" in result["message"]
