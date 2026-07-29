import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from typing import cast

from core.backup import files as backup_files
from core.backup.files import (
    cleanup_old_backups,
    cleanup_router_files,
    download_backup_file,
    sanitize_router_name,
)
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

_BACKUP_LOCKS: dict[str, threading.RLock] = {}
_BACKUP_LOCKS_GUARD = threading.Lock()
MAX_LOCAL_BACKUPS = 10


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
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        suffix = f"{ts}_{uuid.uuid4().hex[:8]}"
        backup_dir = os.path.join(backup_root, file_prefix, "system")
        os.makedirs(backup_dir, exist_ok=True)

        try:
            mikrotik_api.execute_long(
                router_key,
                "system/backup/save",
                **{"name": f"{file_prefix}_{suffix}"},
            )
            mikrotik_api.execute_long(
                router_key,
                "export",
                **{"file": f"{file_prefix}_export_{suffix}"},
            )

            downloaded = []
            methods: list[str] = []
            for fname in [
                f"{file_prefix}_{suffix}.backup",
                f"{file_prefix}_export_{suffix}.rsc",
            ]:
                success, method = download_backup_file(router_key, fname, backup_dir)
                if success:
                    downloaded.append(fname)
                    if method:
                        methods.append(method)

            cleanup_router_files(router_key, f"{file_prefix}_")
            cleanup_router_files(router_key, f"{file_prefix}_export_")
            cleanup_old_backups(backup_dir, f"{file_prefix}_")

            warning = ""
            if downloaded:
                if "ftp" in methods and "http" not in methods:
                    warning = "تم التحميل عبر FTP (قد يكون أبطأ)"
                elif not methods:
                    pass
            else:
                warning = "تم إنشاء الملفات على الراوتر لكن فشل التحميل المحلي"
                logger.warning(
                    f"Full backup created on router but download failed for {router_key}"
                )

            result = {
                "success": True,
                "message": f"تم الباكوب الكامل لـ {router_name}",
                "timestamp": ts,
                "local_path": backup_dir,
                "downloaded": downloaded,
                "created_files": [
                    f"{file_prefix}_{suffix}.backup",
                    f"{file_prefix}_export_{suffix}.rsc",
                ],
            }
            if warning:
                result["warning"] = warning
            logger.info(f"Full backup completed for {router_name}")
            return cast(RouterOSRow, result)
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"Full backup failed for {router_name} "
                f"(error type: {type(e).__name__}): {e}"
            )
            return cast(RouterOSRow, {"success": False, "message": f"فشل نسخ إحتياطى: {str(e)}"})
