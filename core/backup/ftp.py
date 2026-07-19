import ftplib
import logging
import os
import socket

from core.backup.files import get_ftp_port
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)

_ftp_plaintext_warned = False


def _warn_plaintext_ftp() -> None:
    global _ftp_plaintext_warned
    if not _ftp_plaintext_warned:
        _ftp_plaintext_warned = True
        logger.warning(
            "Backup download uses plaintext FTP (port 21); the router password is "
            "transmitted unencrypted. Run the bot only inside an isolated management "
            "network and restrict the FTP service to the bot host (see CLAUDE.md)."
        )


def get_router_ftp_info(router_key: str, ftp_port: int) -> dict | None:
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


def download_files_via_ftp(
    router_key: str, backup_dir: str, files_to_get: list[str]
) -> list[str]:
    ftp_port = get_ftp_port(router_key)
    ftp_info = get_router_ftp_info(router_key, ftp_port)
    if not ftp_info:
        logger.warning(f"FTP download skipped for {router_key}: no credentials")
        return []

    downloaded = []
    try:
        _warn_plaintext_ftp()
        ftp = ftplib.FTP()
        ftp.connect(ftp_info["host"], ftp_info["port"], timeout=10)
        ftp.set_pasv(True)
        ftp.login(ftp_info["user"], ftp_info["password"])
        logger.info(
            f"FTP connected to {ftp_info['host']}:{ftp_info['port']} (passive mode)"
        )

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
        logger.error(
            f"FTP connection failed for {ftp_info['host']}:{ftp_info['port']}: {e}"
        )

    return downloaded


def upload_file_via_ftp(router_key: str, local_path: str, remote_name: str) -> bool:
    ftp_port = get_ftp_port(router_key)
    ftp_info = get_router_ftp_info(router_key, ftp_port)
    if not ftp_info:
        logger.warning(f"FTP upload skipped for {router_key}: no credentials")
        return False

    try:
        _warn_plaintext_ftp()
        ftp = ftplib.FTP()
        ftp.connect(ftp_info["host"], ftp_info["port"], timeout=10)
        ftp.set_pasv(True)
        ftp.login(ftp_info["user"], ftp_info["password"])
        logger.info(
            f"FTP connected to {ftp_info['host']}:{ftp_info['port']} (passive mode)"
        )

        with open(local_path, "rb") as file_handle:
            ftp.storbinary(f"STOR {remote_name}", file_handle)
        logger.info(f"FTP uploaded: {remote_name}")

        ftp.quit()
        return True
    except (OSError, ftplib.Error, EOFError, socket.timeout) as e:
        logger.error(
            f"FTP upload failed for {ftp_info['host']}:{ftp_info['port']}: {e}"
        )
        return False
