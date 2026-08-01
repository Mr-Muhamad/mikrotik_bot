import ftplib
import logging
import os

from librouteros.exceptions import TrapError

from core.backup.files import get_ftp_port
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from utils.formatters import sanitize_log_data

logger = logging.getLogger(__name__)

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


def get_router_ftp_info(router_key: str, ftp_port: int) -> RouterOSRow | None:
    try:
        info = mikrotik_api.get_router_info(router_key)
        return {
            "host": info["host"],
            "user": info["user"],
            "password": info["password"],
            "port": ftp_port,
        }
    except (TrapError, ConnectionError, OSError) as e:
        logger.warning(
            "Cannot get FTP info for %s (error type: %s): %s",
            router_key, type(e).__name__, sanitize_log_data(str(e)),
        )
        return None
    except Exception as e:  # noqa: BLE001 - catch-all: log unexpected errors before returning None
        logger.warning(
            "Cannot get FTP info for %s (error type: %s): %s",
            router_key, type(e).__name__, sanitize_log_data(str(e)),
            exc_info=True,
        )
        return None


def download_files_via_ftp(router_key: str, backup_dir: str, files_to_get: list[str]) -> list[str]:
    ftp_port = get_ftp_port(router_key)
    ftp_info = get_router_ftp_info(router_key, ftp_port)
    if not ftp_info:
        logger.warning("FTP download skipped for %s: no credentials", router_key)
        return []

    downloaded = []
    ftp: ftplib.FTP | None = None
    try:
        _warn_plaintext_ftp()
        ftp = ftplib.FTP()
        host = str(ftp_info["host"])
        port = int(ftp_info["port"] or 21)
        user = str(ftp_info["user"])
        password = str(ftp_info["password"])
        ftp.connect(host, port, timeout=10)
        ftp.set_pasv(True)
        ftp.login(user, password)
        logger.info("FTP connected to %s:%s (passive mode)", ftp_info["host"], ftp_info["port"])

        for fname in files_to_get:
            local_path = os.path.join(backup_dir, fname)
            try:
                with open(local_path, "wb") as file_handle:
                    ftp.retrbinary(f"RETR {fname}", file_handle.write)
                downloaded.append(fname)
                logger.info("FTP downloaded: %s", fname)
            except (TimeoutError, OSError, ftplib.Error, EOFError) as e:
                logger.warning("FTP download failed for %s: %s", fname, e)
    except (TimeoutError, OSError, ftplib.Error, EOFError) as e:
        logger.error("FTP connection failed for %s:%s: %s", ftp_info["host"], ftp_info["port"], e)
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except (ftplib.Error, OSError, EOFError) as e:
                logger.debug("FTP quit error (already closed?): %s", sanitize_log_data(str(e)))
    return downloaded


def upload_file_via_ftp(router_key: str, local_path: str, remote_name: str) -> bool:
    ftp_port = get_ftp_port(router_key)
    ftp_info = get_router_ftp_info(router_key, ftp_port)
    if not ftp_info:
        logger.warning("FTP upload skipped for %s: no credentials", router_key)
        return False

    ftp: ftplib.FTP | None = None
    try:
        _warn_plaintext_ftp()
        ftp = ftplib.FTP()
        host = str(ftp_info["host"])
        port = int(ftp_info["port"] or 21)
        user = str(ftp_info["user"])
        password = str(ftp_info["password"])
        ftp.connect(host, port, timeout=10)
        ftp.set_pasv(True)
        ftp.login(user, password)
        logger.info("FTP connected to %s:%s (passive mode)", ftp_info["host"], ftp_info["port"])

        with open(local_path, "rb") as file_handle:
            ftp.storbinary(f"STOR {remote_name}", file_handle)
        logger.info("FTP uploaded: %s", remote_name)

        return True
    except (TimeoutError, OSError, ftplib.Error, EOFError) as e:
        logger.error("FTP upload failed for %s:%s: %s", ftp_info["host"], ftp_info["port"], e)
        return False
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except (ftplib.Error, OSError, EOFError) as e:
                logger.debug("FTP quit error (already closed?): %s", sanitize_log_data(str(e)))
