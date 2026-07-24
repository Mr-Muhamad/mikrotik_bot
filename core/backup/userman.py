import logging
import os
from datetime import UTC, datetime

from core.backup import files as backup_files
from core.backup.files import (
    USERMAN_BACKUP_PREFIX,
    cleanup_old_files,
    cleanup_router_files,
    sanitize_router_name,
)
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)


class UserManagerBackupService:
    def userman_backup(self, router_key: str, backup_root: str | None = None) -> dict:
        backup_root = backup_root or backup_files.BACKUP_DIR
        router_name = mikrotik_api.get_router_name(router_key)
        file_prefix = f"{USERMAN_BACKUP_PREFIX}{sanitize_router_name(router_name)}"
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        umb_filename = f"{file_prefix}_{timestamp}.umb"
        userman_dir = os.path.join(backup_root, "userman")
        os.makedirs(userman_dir, exist_ok=True)
        umb_path = os.path.join(userman_dir, umb_filename)

        try:
            base_path = mikrotik_api.get_userman_base_path(router_key)
            mikrotik_api.execute_long(
                router_key,
                f"{base_path}/database/save",
                **{"name": umb_filename, "overwrite": "yes"},
            )

            downloaded = []
            if mikrotik_api.download_file_from_router(router_key, umb_filename, userman_dir):
                downloaded.append(umb_filename)
            cleanup_router_files(router_key, f"{file_prefix}_")
            cleanup_old_files(userman_dir, file_prefix)

            result = {
                "success": True,
                "message": f"تم باكوب User Manager لـ {router_name}",
                "timestamp": timestamp,
                "local_path": umb_path,
                "filename": umb_filename,
                "downloaded": downloaded,
            }
            if not downloaded:
                result["warning"] = "تم إنشاء الملف على الراوتر لكن فشل التحميل المحلي"
                logger.warning(
                    f"User Manager backup created on router but HTTP download failed for {router_key}"  # noqa: E501
                )
            logger.info(f"User Manager backup completed for {router_name}: {umb_filename}")
            return result
        except Exception as e:
            logger.error(f"User Manager backup failed for {router_name}: {e}")
            if os.path.isfile(umb_path):
                try:
                    os.remove(umb_path)
                except OSError as cleanup_err:
                    logger.warning(f"Failed to cleanup partial file {umb_path}: {cleanup_err}")
            return {"success": False, "message": f"فشل الباكوب: {str(e)}"}

    def userman_restore(
        self, router_key: str, umb_path: str, backup_root: str | None = None
    ) -> dict:
        router_name = mikrotik_api.get_router_name(router_key)

        if not os.path.isfile(umb_path):
            return {"success": False, "message": "ملف الاسترجاع غير موجود"}

        filename = os.path.basename(umb_path)

        try:
            success = mikrotik_api.upload_file_to_router(router_key, umb_path, filename)
            if not success:
                return {"success": False, "message": "فشل رفع ملف الاستعادة عبر HTTP"}

            base_path = mikrotik_api.get_userman_base_path(router_key)
            mikrotik_api.execute_long(
                router_key, f"{base_path}/database/load", **{"name": filename}
            )

            result = {
                "success": True,
                "message": f"تمت استعادة User Manager لـ {router_name} من ملف {filename}",
            }
            logger.info(f"User Manager restore completed for {router_name}: {filename}")
            return result
        except Exception as e:
            logger.error(f"User Manager restore failed for {router_name}: {e}")
            return {"success": False, "message": f"فشل الاستعادة: {str(e)}"}

    @staticmethod
    def list_local_userman_backups(backup_root: str | None = None) -> list[dict]:
        backup_root = backup_root or backup_files.BACKUP_DIR
        userman_dir = os.path.join(backup_root, "userman")
        if not os.path.isdir(userman_dir):
            return []
        files = []
        for entry in os.listdir(userman_dir):
            full = os.path.join(userman_dir, entry)
            if (
                os.path.isfile(full)
                and (entry.endswith(".umb") or entry.endswith(".tar"))
                and entry.startswith(USERMAN_BACKUP_PREFIX)
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
