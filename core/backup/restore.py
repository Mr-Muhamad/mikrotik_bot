import logging
from core.mikrotik_client import RouterOSRow

from core.backup.files import is_valid_router_backup_name
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)


class BackupRestore:
    def list_router_backups(self, router_key: str) -> list[RouterOSRow]:
        try:
            files = mikrotik_api.execute(router_key, "file/print")
            backups = []
            for item in files:
                name = item.get("name", "")
                if name.startswith("backup_") and name.endswith(".backup"):
                    backups.append(
                        {
                            "name": name,
                            "type": "system",
                            "size": item.get("size", "0"),
                        }
                    )
                elif name.startswith("export_") and name.endswith(".rsc"):
                    backups.append(
                        {
                            "name": name,
                            "type": "export",
                            "size": item.get("size", "0"),
                        }
                    )
            backups.sort(key=lambda x: x["name"], reverse=True)
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups on {router_key}: {e}")
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

            logger.info(f"Restored backup {backup_name} on {router_name}")
            return {
                "success": True,
                "message": f"تمت استعادة النسخة الاحتياطية {backup_name} بنجاح",
            }
        except Exception as e:
            logger.error(f"Failed to restore {backup_name} on {router_name}: {e}")
            return {"success": False, "message": f"فشل الاستعادة: {str(e)}"}
