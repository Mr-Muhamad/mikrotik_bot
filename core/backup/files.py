import logging
import os
import shutil
import tarfile
from datetime import datetime, timezone

from config import BACKUP_DIR
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)

MAX_LOCAL_BACKUPS = 10
MAX_ROUTER_BACKUPS = 5
FTP_PORT = 21
BACKUP_FILE_EXTENSIONS = (".backup", ".rsc", ".tar", ".umb")
USERMAN_BACKUP_PREFIX = "User_Manager_"


def parse_router_creation_time(raw: str | None) -> datetime:
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    for fmt in ("%b/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=timezone.utc)


def get_ftp_port(router_key: str) -> int:
    try:
        services = mikrotik_api.execute(router_key, "ip/service/print")
        for svc in services:
            if svc.get("name", "").lower() == "ftp":
                return int(svc.get("port", FTP_PORT))
    except Exception as e:
        logger.debug(f"Could not fetch FTP port for {router_key}: {e}")
    return FTP_PORT


def sanitize_router_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)
    return safe.strip("_") or "router"


def is_safe_filename(filename: str) -> bool:
    if not isinstance(filename, str) or not filename:
        return False
    if "\x00" in filename or ".." in filename:
        return False
    if "/" in filename or "\\" in filename:
        return False
    return os.path.basename(filename) == filename


def safe_join_file(
    parent_dir: str, filename: str, allowed_extensions: tuple[str, ...]
) -> str:
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


def resolve_userman_backup_file(filename: str, backup_root: str | None = None) -> str:
    if not filename.startswith(USERMAN_BACKUP_PREFIX):
        raise ValueError("اسم نسخة User Manager غير صالح")
    backup_root = backup_root or BACKUP_DIR
    userman_dir = os.path.join(backup_root, "userman")
    return safe_join_file(userman_dir, filename, (".tar", ".umb"))


def is_valid_router_backup_name(filename: str) -> bool:
    if not is_safe_filename(filename):
        return False
    return (
        (filename.startswith("backup_") and filename.endswith(".backup"))
        or (filename.startswith("export_") and filename.endswith(".rsc"))
        or (filename.startswith(USERMAN_BACKUP_PREFIX) and filename.endswith(".umb"))
    )


def validate_tar_members(tar: tarfile.TarFile, extract_dir: str) -> None:
    extract_abs = os.path.abspath(extract_dir)
    for member in tar.getmembers():
        member_name = member.name
        if not member_name or os.path.isabs(member_name) or "\x00" in member_name:
            raise ValueError("أرشيف الاستعادة يحتوي مساراً غير صالح")
        member_path = os.path.abspath(os.path.join(extract_abs, member_name))
        if os.path.commonpath([extract_abs, member_path]) != extract_abs:
            raise ValueError("أرشيف الاستعادة يحاول الكتابة خارج مجلد الاستعادة")


def cleanup_old_backups(
    parent_dir: str, router_key: str, keep: int = MAX_LOCAL_BACKUPS
) -> int:
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
            logger.warning(f"Failed to delete old backup {path}: {e}")
    if deleted:
        logger.info(
            f"Cleaned up {deleted} old backup(s) for {router_key} in {parent_dir}"
        )
    return deleted


def cleanup_old_files(
    parent_dir: str, prefix: str, keep: int = MAX_LOCAL_BACKUPS
) -> int:
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
            logger.warning(f"Failed to delete old tar {path}: {e}")
    if deleted:
        logger.info(
            f"Cleaned up {deleted} old tar(s) with prefix {prefix} in {parent_dir}"
        )
    return deleted


def cleanup_router_files(
    router_key: str, pattern_prefix: str, keep: int = MAX_ROUTER_BACKUPS
) -> int:
    deleted = 0
    try:
        files = mikrotik_api.execute(router_key, "file/print")
        matching = []
        for item in files:
            name = item.get("name", "")
            if name.startswith(pattern_prefix) and not name.endswith(".txt"):
                matching.append(item)

        matching.sort(
            key=lambda x: parse_router_creation_time(x.get("creation-time")),
            reverse=True,
        )

        for item in matching[keep:]:
            name = item.get("name", "")
            try:
                mikrotik_api.execute(
                    router_key, "file/remove", **{".id": item.get(".id")}
                )
                deleted += 1
                logger.debug(f"Removed old router file: {name}")
            except Exception as e:
                logger.debug(f"Failed to remove router file {name}: {e}")
    except Exception as e:
        logger.warning(f"Failed to list router files for cleanup: {e}")
    return deleted
