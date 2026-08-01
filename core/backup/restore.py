import logging

from librouteros.exceptions import TrapError

from core.backup.files import is_valid_router_backup_name, sanitize_router_name
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from utils.formatters import sanitize_log_data

logger = logging.getLogger(__name__)


class BackupRestore:
    def list_router_backups(self, router_key: str) -> list[RouterOSRow]:
        try:
            router_name = mikrotik_api.get_router_name(router_key)
            file_prefix = sanitize_router_name(router_name)
            files = mikrotik_api.execute(router_key, "file/print")
            backups = []
            for item in files:
                name = str(item.get("name", ""))
                # Match system backups (either prefix-based or backup_*)
                if name.endswith(".backup") and (name.startswith(f"{file_prefix}_") or name.startswith("backup_")):
                    backups.append(
                        {
                            "name": name,
                            "type": "system",
                            "size": str(item.get("size", "0")),
                        }
                    )
                elif name.endswith(".rsc") and (name.startswith(f"{file_prefix}_") or name.startswith("export_")):
                    backups.append(
                        {
                            "name": name,
                            "type": "export",
                            "size": str(item.get("size", "0")),
                        }
                    )
            backups.sort(key=lambda x: x["name"], reverse=True)
            return backups
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Failed to list backups on %s (error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return []
        except Exception as e:  # noqa: BLE001 - catch-all: log unexpected errors before returning empty list
            logger.exception(
                "Failed to list backups on %s (error type: %s): %s",
                router_key, type(e).__name__, sanitize_log_data(str(e)),
            )
            return []

    def restore_backup(self, router_key: str, backup_name: str) -> RouterOSRow:
        router_name = mikrotik_api.get_router_name(router_key)
        try:
            if not is_valid_router_backup_name(backup_name):
                return {
                    "success": False,
                    "message": "اسم ملف النسخة الاحتياطية غير صالح",
                }

            if backup_name.endswith(".backup"):
                mikrotik_api.execute_long(router_key, "system/backup/load", **{"name": backup_name})
            elif backup_name.endswith(".rsc"):
                mikrotik_api.execute_long(router_key, "import", **{"file": backup_name})
            else:
                return {"success": False, "message": "نوع ملف غير معروف"}

            logger.info("Restored backup %s on %s", backup_name, router_name)
            return {
                "success": True,
                "message": f"تمت استعادة النسخة الاحتياطية {backup_name} بنجاح",
            }
        except (TrapError, ConnectionError, OSError) as e:
            logger.error(
                "Failed to restore %s on %s (error type: %s): %s",
                backup_name, router_name, type(e).__name__, sanitize_log_data(str(e)),
            )
            return {"success": False, "message": f"فشل الاستعادة: {sanitize_log_data(str(e))}"}
        except Exception as e:  # noqa: BLE001 - catch-all: log unexpected errors before returning failure result
            logger.exception(
                "Failed to restore %s on %s (error type: %s): %s",
                backup_name, router_name, type(e).__name__, sanitize_log_data(str(e)),
            )
            return {"success": False, "message": f"فشل الاستعادة: {sanitize_log_data(str(e))}"}
