import logging
import os
from datetime import UTC, datetime
from typing import cast

from core.backup import files as backup_files
from core.backup.files import (
    USERMAN_BACKUP_PREFIX,
    cleanup_old_files,
    cleanup_router_files,
    download_backup_file,
    sanitize_router_name,
)
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)


class UserManagerBackupService:
    def userman_backup(self, router_key: str, backup_root: str | None = None) -> RouterOSRow:
        backup_root = backup_root or backup_files.BACKUP_DIR
        router_name = mikrotik_api.get_router_name(router_key)
        router_safe = sanitize_router_name(router_name)
        file_prefix = f"{USERMAN_BACKUP_PREFIX}{router_safe}"
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        umb_filename = f"{file_prefix}_{timestamp}.umb"
        userman_dir = os.path.join(backup_root, router_safe, "userman")
        os.makedirs(userman_dir, exist_ok=True)
        umb_path = os.path.join(userman_dir, umb_filename)

        try:
            base_path = mikrotik_api.get_userman_base_path(router_key)
            mikrotik_api.execute_long(
                router_key,
                f"{base_path}/database/save",
                **{"name": umb_filename, "overwrite": "yes"},
            )

            downloaded: list[str] = []
            success, method = download_backup_file(router_key, umb_filename, userman_dir)
            if success:
                downloaded.append(umb_filename)
            else:
                logger.warning(
                    f"User Manager backup file {umb_filename} not downloaded for {router_key}"
                )
            cleanup_router_files(router_key, f"{file_prefix}_")
            cleanup_old_files(userman_dir, file_prefix)

            warning = ""
            if downloaded:
                if method == "ftp":
                    warning = "تم التحميل عبر FTP (قد يكون أبطأ)"
            else:
                warning = "تم إنشاء الملف على الراوتر لكن فشل التحميل المحلي"
                logger.warning(
                    f"User Manager backup created on router but download failed for {router_key}"
                )

            result = {
                "success": True,
                "message": f"تم باكوب User Manager لـ {router_name}",
                "timestamp": timestamp,
                "local_path": userman_dir,
                "filename": umb_filename,
                "downloaded": downloaded,
                "created_files": [umb_filename],
            }
            if warning:
                result["warning"] = warning
            logger.info(f"User Manager backup completed for {router_name}: {umb_filename}")
            return cast(RouterOSRow, result)
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"User Manager backup failed for {router_name} "
                f"(error type: {type(e).__name__}): {e}"
            )
            if os.path.isfile(umb_path):
                try:
                    os.remove(umb_path)
                except OSError as cleanup_err:
                    logger.warning(f"Failed to cleanup partial file {umb_path}: {cleanup_err}")
            return cast(RouterOSRow, {"success": False, "message": f"فشل الباكوب: {str(e)}"})

    def userman_restore(
        self, router_key: str, umb_path: str, backup_root: str | None = None
    ) -> RouterOSRow:
        router_name = mikrotik_api.get_router_name(router_key)

        if not os.path.isfile(umb_path):
            return cast(RouterOSRow, {"success": False, "message": "ملف الاسترجاع غير موجود"})

        filename = os.path.basename(umb_path)

        try:
            success = mikrotik_api.upload_file_to_router(router_key, umb_path, filename)
            if not success:
                return cast(
                    RouterOSRow, {"success": False, "message": "فشل رفع ملف الاستعادة عبر HTTP"}
                )

            base_path = mikrotik_api.get_userman_base_path(router_key)
            mikrotik_api.execute_long(
                router_key, f"{base_path}/database/load", **{"name": filename}
            )

            result = {
                "success": True,
                "message": f"تمت استعادة User Manager لـ {router_name} من ملف {filename}",
            }
            logger.info(f"User Manager restore completed for {router_name}: {filename}")
            return cast(RouterOSRow, result)
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"User Manager restore failed for {router_name} "
                f"(error type: {type(e).__name__}): {e}"
            )
            return cast(RouterOSRow, {"success": False, "message": f"فشل الاستعادة: {str(e)}"})

    @staticmethod
    def list_local_userman_backups(
        router_key: str = "", backup_root: str | None = None
    ) -> list[RouterOSRow]:
        if router_key and (os.path.isdir(router_key) or "/" in router_key or "\\" in router_key):
            backup_root = router_key
            router_key = ""

        backup_root = backup_root or backup_files.BACKUP_DIR

        if not router_key:
            userman_dir = os.path.join(backup_root, "userman")
            prefix = USERMAN_BACKUP_PREFIX
        else:
            router_name = mikrotik_api.get_router_name(router_key)
            router_safe = sanitize_router_name(router_name)
            userman_dir = os.path.join(backup_root, router_safe, "userman")
            prefix = f"{USERMAN_BACKUP_PREFIX}{router_safe}"

        if not os.path.isdir(userman_dir):
            return []

        files = []
        for entry in os.listdir(userman_dir):
            full = os.path.join(userman_dir, entry)
            if (
                os.path.isfile(full)
                and (entry.endswith(".umb") or entry.endswith(".tar"))
                and entry.startswith(prefix)
            ):
                stat = os.stat(full)
                files.append(
                    {
                        "filename": entry,
                        "path": full,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )
        files.sort(key=lambda item: item["mtime"], reverse=True)
        return files
