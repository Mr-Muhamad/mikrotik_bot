import ftplib
import logging
import os
import shutil
import socket
from datetime import datetime, timezone

from core.backup import files as backup_files
from core.backup.files import cleanup_old_backups, cleanup_router_files, get_ftp_port, sanitize_router_name
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)

# Plaintext FTP transmits the router password unencrypted. This project operates
# inside an isolated management network (see AGENTS.md); this warning makes the
# exposure explicit. Switch to SFTP (e.g. paramiko) if the routers expose SSH.
_ftp_plaintext_warned = False


def _warn_plaintext_ftp() -> None:
    global _ftp_plaintext_warned
    if not _ftp_plaintext_warned:
        _ftp_plaintext_warned = True
        logger.warning(
            "Backup download uses plaintext FTP (port 21); the router password is "
            "transmitted unencrypted. Run the bot only inside an isolated management "
            "network and restrict the FTP service to the bot host (see AGENTS.md)."
        )


class SystemBackupService:
    def get_router_ftp_info(self, router_key: str, ftp_port: int) -> dict | None:
        try:
            info = mikrotik_api.get_router_info(router_key)
            return {
                "host": info["host"],
                "user": info["user"],
                "password": info["password"],
                "port": ftp_port,
            }
        except Exception as e:
            logger.warning(f"Cannot get FTP info for {router_key}: {e}")
            return None

    def download_files_via_ftp(self, router_key: str, backup_dir: str, timestamp: str, file_prefix: str) -> list[str]:
        ftp_port = get_ftp_port(router_key)
        ftp_info = self.get_router_ftp_info(router_key, ftp_port)
        if not ftp_info:
            logger.warning(f"FTP download skipped for {router_key}: no credentials")
            return []

        downloaded = []
        backup_name = f"{file_prefix}_{timestamp}.backup"
        export_name = f"{file_prefix}_export_{timestamp}.rsc"
        files_to_get = [backup_name, export_name]

        try:
            _warn_plaintext_ftp()
            ftp = ftplib.FTP()
            ftp.connect(ftp_info["host"], ftp_info["port"], timeout=10)
            ftp.set_pasv(True)
            ftp.login(ftp_info["user"], ftp_info["password"])
            logger.info(f"FTP connected to {ftp_info['host']}:{ftp_info['port']} (passive mode)")

            for fname in files_to_get:
                local_path = os.path.join(backup_dir, fname)
                try:
                    with open(local_path, "wb") as file_handle:
                        ftp.retrbinary(f"RETR {fname}", file_handle.write)
                    downloaded.append(fname)
                    logger.info(f"FTP downloaded: {fname}")
                except (OSError, ftplib.Error, EOFError, socket.timeout) as e:
                    logger.warning(f"FTP download failed for {fname}: {e}")

            ftp.quit()
        except (OSError, ftplib.Error, EOFError, socket.timeout) as e:
            logger.error(f"FTP connection failed for {ftp_info['host']}:{ftp_info['port']}: {e}")

        return downloaded

    def full_backup(self, router_key: str, backup_root: str | None = None) -> dict:
        router_name = mikrotik_api.get_router_name(router_key)
        backup_root = backup_root or backup_files.BACKUP_DIR
        file_prefix = sanitize_router_name(router_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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

            downloaded = self.download_files_via_ftp(router_key, backup_dir, timestamp, file_prefix)
            cleanup_router_files(router_key, f"{file_prefix}_")
            cleanup_router_files(router_key, f"{file_prefix}_export_")

            parent = os.path.dirname(backup_dir)
            cleanup_old_backups(parent, file_prefix)

            result = {
                "success": True,
                "message": f"تم الباكوب الكامل لـ {router_name}",
                "timestamp": timestamp,
                "local_path": backup_dir,
                "downloaded": downloaded,
            }
            if not downloaded:
                result["warning"] = "تم إنشاء الملفات على الراوتر لكن فشل التحميل المحلي"
                logger.warning(f"Full backup created on router but FTP download failed for {router_key}")
            logger.info(f"Full backup completed for {router_name}")
            return result
        except Exception as e:
            logger.error(f"Full backup failed for {router_name}: {e}")
            if os.path.isdir(backup_dir):
                try:
                    shutil.rmtree(backup_dir)
                except OSError:
                    pass
            return {"success": False, "message": f"فشل نسخ إحتياطى: {str(e)}"}
