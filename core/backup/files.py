import logging
import os
import shutil
import tarfile
from datetime import UTC, datetime

from librouteros.exceptions import LibRouterosError

from config import BACKUP_DIR
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)

MAX_LOCAL_BACKUPS = 10
MAX_ROUTER_BACKUPS = 5
BACKUP_FILE_EXTENSIONS = (".backup", ".rsc", ".tar", ".umb")
USERMAN_BACKUP_PREFIX = "User_Manager_"


def get_ftp_port(router_key: str = "") -> int:
    """Return default FTP port (21)."""
    return 21


def parse_router_creation_time(raw: str | None) -> datetime:
    if not raw:
        return datetime.min.replace(tzinfo=UTC)
    for fmt in ("%b/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=UTC)


def sanitize_router_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)
    return safe.strip("_") or "router"


def is_safe_filename(filename: str) -> bool:
    if not filename:
        return False
    if "\x00" in filename or ".." in filename:
        return False
    if "/" in filename or "\\" in filename:
        return False
    return os.path.basename(filename) == filename


def safe_join_file(parent_dir: str, filename: str, allowed_extensions: tuple[str, ...]) -> str:
    if not is_safe_filename(filename):
        raise ValueError("اسم الملف غير صالح")
    if not filename.endswith(allowed_extensions):
        raise ValueError("نوع الملف غير مسموح")

    parent_abs = os.path.abspath(parent_dir)
    target_abs = os.path.abspath(os.path.join(parent_abs, filename))
    if os.path.commonpath([parent_abs, target_abs]) != parent_abs:
        raise ValueError("مسار الملف غير صالح")
    return target_abs


def resolve_local_backup_file(parent_dir: str, filename: str) -> str:
    return safe_join_file(parent_dir, filename, BACKUP_FILE_EXTENSIONS)


def resolve_userman_backup_file(
    filename: str,
    backup_root: str | None = None,
    router_name: str | None = None,
) -> str:
    if not filename.startswith(USERMAN_BACKUP_PREFIX):
        raise ValueError("اسم نسخة User Manager غير صالح")
    backup_root = backup_root or BACKUP_DIR
    if router_name:
        userman_dir = os.path.join(backup_root, sanitize_router_name(router_name), "userman")
    else:
        userman_dir = os.path.join(backup_root, "userman")
    return safe_join_file(userman_dir, filename, (".tar", ".umb"))


def is_valid_router_backup_name(filename: str) -> bool:
    if not is_safe_filename(filename):
        return False
    return filename.endswith((".backup", ".rsc", ".umb"))


def validate_tar_members(tar: tarfile.TarFile, extract_dir: str) -> None:
    extract_abs = os.path.abspath(extract_dir)
    for member in tar.getmembers():
        member_name = member.name
        if not member_name or os.path.isabs(member_name) or "\x00" in member_name:
            raise ValueError("أرشيف الاستعادة يحتوي مساراً غير صالح")
        member_path = os.path.abspath(os.path.join(extract_abs, member_name))
        if os.path.commonpath([extract_abs, member_path]) != extract_abs:
            raise ValueError("أرشيف الاستعادة يحاول الكتابة خارج مجلد الاستعادة")


def cleanup_old_backups(parent_dir: str, router_key: str, keep: int = MAX_LOCAL_BACKUPS) -> int:
    if not os.path.isdir(parent_dir):
        return 0
    dirs = []
    for entry in os.listdir(parent_dir):
        full = os.path.join(parent_dir, entry)
        if os.path.isdir(full) and entry.startswith(router_key + "_"):
            dirs.append((os.path.getmtime(full), full))
    if len(dirs) <= keep:
        return 0
    dirs.sort()
    deleted = 0
    for _, path in dirs[:-keep]:
        try:
            shutil.rmtree(path)
            deleted += 1
        except OSError as e:
            logger.warning("Failed to delete old backup %s: %s", path, e)
    if deleted:
        logger.info("Cleaned up %d old backup(s) for %s in %s", deleted, router_key, parent_dir)
    return deleted


def cleanup_old_files(parent_dir: str, prefix: str, keep: int = MAX_LOCAL_BACKUPS) -> int:
    if not os.path.isdir(parent_dir):
        return 0
    files = []
    for entry in os.listdir(parent_dir):
        full = os.path.join(parent_dir, entry)
        if (
            os.path.isfile(full)
            and entry.startswith(prefix)
            and (entry.endswith(".tar") or entry.endswith(".umb"))
        ):
            files.append((os.path.getmtime(full), full))
    if len(files) <= keep:
        return 0
    files.sort()
    deleted = 0
    for _, path in files[:-keep]:
        try:
            os.remove(path)
            deleted += 1
        except OSError as e:
            logger.warning("Failed to delete old tar %s: %s", path, e)
    if deleted:
        logger.info("Cleaned up %d old tar(s) with prefix %s in %s", deleted, prefix, parent_dir)
    return deleted


def download_backup_file(router_key: str, remote_name: str, local_dir: str) -> tuple[bool, str]:
    """
    Download a backup file from router to local_dir.

    Tries HTTP push first, then FTP as fallback.

    Returns:
        (success, method) where method = ``"http"``, ``"ftp"``, or ``""``.
    """
    # 1. Try HTTP push (router pushes file to bot's file server)
    if mikrotik_api.download_file_from_router(router_key, remote_name, local_dir):
        return True, "http"

    # 2. FTP fallback
    try:
        from core.backup.ftp import download_files_via_ftp  # noqa: PLC0415 - avoid circular import

        downloaded = download_files_via_ftp(router_key, local_dir, [remote_name])
        if remote_name in downloaded:
            return True, "ftp"
    except Exception:  # noqa: BLE001 - catch-all safe: FTP is best-effort fallback
        logger.debug("FTP fallback failed for %s on %s", remote_name, router_key, exc_info=True)

    return False, ""


def cleanup_router_files(
    router_key: str, pattern_prefix: str, keep: int = MAX_ROUTER_BACKUPS
) -> int:
    deleted = 0
    try:
        files = mikrotik_api.execute(router_key, "file/print")
        matching = []
        for item in files:
            name = str(item.get("name", ""))
            if name.startswith(pattern_prefix) and not name.endswith(".txt"):
                matching.append(item)

        matching.sort(
            key=lambda x: parse_router_creation_time(x.get("creation-time")),
            reverse=True,
        )

        for item in matching[keep:]:
            name = item.get("name", "")
            try:
                mikrotik_api.execute(router_key, "file/remove", **{".id": item.get(".id")})
                deleted += 1
                logger.debug("Removed old router file: %s", name)
            except (LibRouterosError, OSError) as e:
                logger.debug("Failed to remove router file %s: %s", name, e)
    except (LibRouterosError, OSError) as e:
        logger.warning("Failed to list router files for cleanup: %s", e)
    return deleted
