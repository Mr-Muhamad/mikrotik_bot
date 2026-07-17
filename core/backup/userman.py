import json
import logging
import os
import shutil
import tarfile
from datetime import datetime, timezone

from core.backup import files as backup_files
from core.backup.files import USERMAN_BACKUP_PREFIX, cleanup_old_files, sanitize_router_name, validate_tar_members
from core.mikrotik_api import mikrotik_api

logger = logging.getLogger(__name__)

_PROFILE_OPTIONAL_FIELDS = (
    "uptime",
    "address-list",
    "idle-timeout",
    "keepalive-timeout",
    "status-autorefresh",
    "session-timeout",
)

_FIELD_REJECT_MARKERS = (
    "unknown parameter",
    "unknown property",
    "no such item",
    "expected end",
    "unknown command",
)


class UserManagerBackupService:
    def userman_backup(self, router_key: str, backup_root: str | None = None) -> dict:
        backup_root = backup_root or backup_files.BACKUP_DIR
        router_name = mikrotik_api.get_router_name(router_key)
        file_prefix = f"{USERMAN_BACKUP_PREFIX}{sanitize_router_name(router_name)}"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        tar_filename = f"{file_prefix}_{timestamp}.tar"
        userman_dir = os.path.join(backup_root, "userman")
        os.makedirs(userman_dir, exist_ok=True)
        tar_path = os.path.join(userman_dir, tar_filename)

        temp_dir = os.path.join(userman_dir, f"_tmp_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            base_path = mikrotik_api.get_userman_base_path(router_key)
            users = mikrotik_api.execute(router_key, f"{base_path}/user/print")
            profiles = mikrotik_api.execute(router_key, f"{base_path}/profile/print")

            profiles_file = os.path.join(temp_dir, "profiles.json")
            with open(profiles_file, "w", encoding="utf-8") as file_handle:
                json.dump(profiles, file_handle, ensure_ascii=False, indent=2)

            users_file = os.path.join(temp_dir, "users.json")
            sanitized = [dict(user) for user in users]
            with open(users_file, "w", encoding="utf-8") as file_handle:
                json.dump(sanitized, file_handle, ensure_ascii=False, indent=2)

            metadata = {
                "router": router_name,
                "router_key": router_key,
                "timestamp": timestamp,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "users_count": len(users),
                "profiles_count": len(profiles),
                "version": "1.0",
            }
            meta_file = os.path.join(temp_dir, "metadata.json")
            with open(meta_file, "w", encoding="utf-8") as file_handle:
                json.dump(metadata, file_handle, ensure_ascii=False, indent=2)

            with tarfile.open(tar_path, "w") as tar:
                tar.add(profiles_file, arcname="profiles.json")
                tar.add(users_file, arcname="users.json")
                tar.add(meta_file, arcname="metadata.json")

            shutil.rmtree(temp_dir, ignore_errors=True)
            cleanup_old_files(userman_dir, file_prefix)

            logger.info(f"User Manager backup completed for {router_name}: {tar_filename}")
            return {
                "success": True,
                "message": f"تم باكوب User Manager لـ {router_name}",
                "timestamp": timestamp,
                "local_path": tar_path,
                "filename": tar_filename,
                "users_count": len(users),
                "profiles_count": len(profiles),
            }
        except Exception as e:
            logger.error(f"User Manager backup failed for {router_name}: {e}")
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.isfile(tar_path):
                try:
                    os.remove(tar_path)
                except OSError as cleanup_err:
                    logger.warning(f"Failed to cleanup partial tar file {tar_path}: {cleanup_err}")
            return {"success": False, "message": f"فشل الباكوب: {str(e)}"}

    @staticmethod
    def _profile_add_args(name: str, profile: dict) -> dict:
        add_args = {"name": name, "shared-users": profile.get("shared-users", 1)}
        for field in _PROFILE_OPTIONAL_FIELDS:
            if profile.get(field) is not None:
                add_args[field] = profile[field]
        return add_args

    @staticmethod
    def _user_add_args(name: str, user: dict) -> dict:
        args = {
            "name": name,
            "password": user.get("password", ""),
            "profile": user.get("profile", "default"),
        }
        if user.get("caller-id"):
            args["caller-id"] = user["caller-id"]
        return args

    @staticmethod
    def _is_field_rejection(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(marker in msg for marker in _FIELD_REJECT_MARKERS)

    def userman_restore(self, router_key: str, tar_path: str, backup_root: str | None = None) -> dict:
        backup_root = backup_root or backup_files.BACKUP_DIR
        router_name = mikrotik_api.get_router_name(router_key)
        result = {
            "success": True,
            "users_restored": 0,
            "profiles_restored": 0,
            "errors": [],
            "skipped": {"users": 0, "profiles": 0},
        }

        if not os.path.isfile(tar_path):
            return {"success": False, "message": "ملف الاسترجاع غير موجود"}

        try:
            base_path = mikrotik_api.get_userman_base_path(router_key)
            temp_dir = os.path.join(
                backup_root,
                "userman",
                f"_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            )
            os.makedirs(temp_dir, exist_ok=True)

            try:
                with tarfile.open(tar_path, "r") as tar:
                    validate_tar_members(tar, temp_dir)
                    tar.extractall(path=temp_dir, filter="data")

                profiles = []
                profiles_path = os.path.join(temp_dir, "profiles.json")
                if os.path.isfile(profiles_path):
                    with open(profiles_path, "r", encoding="utf-8") as file_handle:
                        profiles = json.load(file_handle)

                users = []
                users_path = os.path.join(temp_dir, "users.json")
                if os.path.isfile(users_path):
                    with open(users_path, "r", encoding="utf-8") as file_handle:
                        users = json.load(file_handle)

                existing_profiles = mikrotik_api.execute(router_key, f"{base_path}/profile/print")
                existing_profile_names = {profile.get("name") for profile in existing_profiles}

                for profile in profiles:
                    name = profile.get("name")
                    if not name:
                        continue
                    if name in existing_profile_names:
                        result["skipped"]["profiles"] += 1
                        continue
                    try:
                        mikrotik_api.execute_long(
                            router_key,
                            f"{base_path}/profile/add",
                            **self._profile_add_args(name, profile),
                        )
                        result["profiles_restored"] += 1
                    except Exception as e:
                        if self._is_field_rejection(e):
                            try:
                                mikrotik_api.execute_long(
                                    router_key,
                                    f"{base_path}/profile/add",
                                    name=name,
                                    **{"shared-users": profile.get("shared-users", 1)},
                                )
                                result["profiles_restored"] += 1
                                continue
                            except Exception as e2:
                                e = e2
                        err_msg = f"فشل استيراد البروفايل '{name}': {e}"
                        logger.warning(err_msg)
                        result["errors"].append(err_msg)

                existing_users = mikrotik_api.execute(router_key, f"{base_path}/user/print")
                existing_user_names = {user.get("name") for user in existing_users}

                for user in users:
                    name = user.get("name")
                    if not name:
                        continue
                    if name in existing_user_names:
                        result["skipped"]["users"] += 1
                        continue
                    try:
                        mikrotik_api.execute_long(
                            router_key,
                            f"{base_path}/user/add",
                            **self._user_add_args(name, user),
                        )
                        result["users_restored"] += 1
                    except Exception as e:
                        if self._is_field_rejection(e):
                            try:
                                mikrotik_api.execute_long(
                                    router_key,
                                    f"{base_path}/user/add",
                                    name=name,
                                    password=user.get("password", ""),
                                    profile=user.get("profile", "default"),
                                )
                                result["users_restored"] += 1
                                continue
                            except Exception as e2:
                                e = e2
                        err_msg = f"فشل استيراد المستخدم '{name}': {e}"
                        logger.warning(err_msg)
                        result["errors"].append(err_msg)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            summary_parts = []
            if result["profiles_restored"]:
                summary_parts.append(f"{result['profiles_restored']} بروفايل")
            if result["users_restored"]:
                summary_parts.append(f"{result['users_restored']} مستخدم")
            if result["skipped"]["profiles"] or result["skipped"]["users"]:
                skipped_total = result["skipped"]["profiles"] + result["skipped"]["users"]
                summary_parts.append(f"{skipped_total} تم تخطيها (موجودة مسبقاً)")

            summary = "، ".join(summary_parts) if summary_parts else "لا شيء"
            result["message"] = f"تمت الاستعادة لـ {router_name}: {summary}"
            if result["errors"]:
                result["message"] += f" مع {len(result['errors'])} خطأ"
                result["success"] = False

            logger.info(f"User Manager restore completed for {router_name}: {summary}")
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
            if os.path.isfile(full) and entry.endswith(".tar") and entry.startswith(USERMAN_BACKUP_PREFIX):
                stat = os.stat(full)
                files.append({
                    "filename": entry,
                    "path": full,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
        files.sort(key=lambda item: item["mtime"], reverse=True)
        return files
