import logging
import os
import shutil
import threading
from datetime import UTC, datetime
from typing import cast

from core.backup import files as backup_files
from core.backup.files import (
    cleanup_old_backups,
    cleanup_router_files,
    sanitize_router_name,
)
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

_BACKUP_LOCKS: dict[str, threading.RLock] = {}
_BACKUP_LOCKS_GUARD = threading.Lock()


def _get_backup_lock(router_key: str) -> threading.RLock:
    with _BACKUP_LOCKS_GUARD:
        if router_key not in _BACKUP_LOCKS:
            _BACKUP_LOCKS[router_key] = threading.RLock()
        return _BACKUP_LOCKS[router_key]


class SystemBackupService:
    def full_backup(self, router_key: str, backup_root: str | None = None) -> RouterOSRow:
        lock = _get_backup_lock(router_key)
        if not lock.acquire(blocking=False):
            return {
                "success": False,
                "message": (
                    "⚠️ توجد عملية نسخ احتياطي جارية حالياً لهذا الراوتر."
                    " الرجاء الانتظار حتى تكتمل."
                ),
            }

        try:
            return self._full_backup_internal(router_key, backup_root)
        finally:
            lock.release()

    def _full_backup_internal(self, router_key: str, backup_root: str | None = None) -> RouterOSRow:
        router_name = mikrotik_api.get_router_name(router_key)
        backup_root = backup_root or backup_files.BACKUP_DIR
        file_prefix = sanitize_router_name(router_name)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(backup_root, "system", f"{file_prefix}_{timestamp}")
        os.makedirs(backup_dir, exist_ok=True)

        try:
            mikrotik_api.execute_long(
                router_key,
                "system/backup/save",
                **{"name": f"{file_prefix}_{timestamp}"},
            )
            mikrotik_api.execute_long(
                router_key,
                "export",
                **{"file": f"{file_prefix}_export_{timestamp}"},
            )

            downloaded = []
            for fname in [
                f"{file_prefix}_{timestamp}.backup",
                f"{file_prefix}_export_{timestamp}.rsc",
            ]:
                if mikrotik_api.download_file_from_router(router_key, fname, backup_dir):
                    downloaded.append(fname)
            cleanup_router_files(router_key, f"{file_prefix}_")
            cleanup_router_files(router_key, f"{file_prefix}_export_")

            parent = os.path.dirname(backup_dir)
            cleanup_old_backups(parent, file_prefix)

            result = {
                "success": True,
                "message": f"تم الباكوب الكامل لـ {router_name}",
                "timestamp": timestamp,
                "local_path": backup_dir,
                "downloaded": str(downloaded),
            }
            if not downloaded:
                result["warning"] = "تم إنشاء الملفات على الراوتر لكن فشل التحميل المحلي"
                logger.warning(
                    f"Full backup created on router but FTP download failed for {router_key}"
                )
            logger.info(f"Full backup completed for {router_name}")
            return cast(RouterOSRow, result)
        except Exception as e:
            logger.error(f"Full backup failed for {router_name}: {e}")
            if os.path.isdir(backup_dir):
                try:
                    shutil.rmtree(backup_dir)
                except OSError as cleanup_err:
                    logger.warning(
                        f"Failed to cleanup partial backup directory {backup_dir}: {cleanup_err}"
                    )
            return cast(RouterOSRow, {"success": False, "message": f"فشل نسخ إحتياطى: {str(e)}"})
