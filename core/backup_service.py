from config import BACKUP_DIR
from core.backup.files import (
    BACKUP_FILE_EXTENSIONS,
    MAX_LOCAL_BACKUPS,
    MAX_ROUTER_BACKUPS,
    USERMAN_BACKUP_PREFIX,
    resolve_local_backup_file,
)
from core.backup.files import (
    resolve_userman_backup_file as _resolve_userman_backup_file,
)
from core.backup.restore import BackupRestore
from core.backup.system import SystemBackupService
from core.backup.userman import UserManagerBackupService
from core.mikrotik_client import RouterOSRow


class BackupService:
    def __init__(
        self,
        system_service: SystemBackupService | None = None,
        userman_service: UserManagerBackupService | None = None,
    ):
        self._system_service = system_service or SystemBackupService()
        self._userman_service = userman_service or UserManagerBackupService()

    def full_backup(self, router_key: str) -> RouterOSRow:
        return self._system_service.full_backup(router_key, backup_root=BACKUP_DIR)

    def userman_backup(self, router_key: str) -> RouterOSRow:
        return self._userman_service.userman_backup(router_key, backup_root=BACKUP_DIR)

    def userman_restore(self, router_key: str, tar_path: str) -> RouterOSRow:
        return self._userman_service.userman_restore(router_key, tar_path, backup_root=BACKUP_DIR)

    @staticmethod
    def list_local_userman_backups(router_key: str = "") -> list[RouterOSRow]:
        return UserManagerBackupService.list_local_userman_backups(router_key=router_key, backup_root=BACKUP_DIR)


def resolve_userman_backup_file(filename: str, router_name: str = "") -> str:
    return _resolve_userman_backup_file(
        filename, backup_root=BACKUP_DIR, router_name=router_name or None
    )


backup_service = BackupService()
backup_restore = BackupRestore()

__all__ = [
    "BACKUP_DIR",
    "BACKUP_FILE_EXTENSIONS",
    "MAX_LOCAL_BACKUPS",
    "MAX_ROUTER_BACKUPS",
    "USERMAN_BACKUP_PREFIX",
    "BackupService",
    "BackupRestore",
    "backup_service",
    "backup_restore",
    "resolve_local_backup_file",
    "resolve_userman_backup_file",
]
