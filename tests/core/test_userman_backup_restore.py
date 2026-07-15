"""Tests for UserManagerBackupService.userman_restore (priority 5 — defensive restore)."""
import json
import tarfile

import pytest
from librouteros.exceptions import LibRouterosError
from unittest.mock import MagicMock

from core.backup.userman import UserManagerBackupService


def _make_tar(tmp_path, profiles, users):
    src = tmp_path / "src"
    src.mkdir()
    (src / "profiles.json").write_text(json.dumps(profiles), encoding="utf-8")
    (src / "users.json").write_text(json.dumps(users), encoding="utf-8")
    (src / "metadata.json").write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    tar_path = tmp_path / "um_backup.tar"
    with tarfile.open(tar_path, "w") as tar:
        tar.add(src / "profiles.json", arcname="profiles.json")
        tar.add(src / "users.json", arcname="users.json")
        tar.add(src / "metadata.json", arcname="metadata.json")
    return str(tar_path)


@pytest.fixture
def svc():
    return UserManagerBackupService()


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.get_router_name.return_value = "TestRouter"
    api.get_userman_base_path.return_value = "user-manager"
    return api


def test_restores_profiles_and_users(svc, tmp_path, mock_api, monkeypatch):
    tar = _make_tar(
        tmp_path,
        [{"name": "p1", "shared-users": 2}],
        [{"name": "u1", "password": "pw", "profile": "default"}],
    )

    def side(rk, command, **kwargs):
        if command.endswith("/print"):
            return []
        if command.endswith("/add"):
            return [{"name": kwargs.get("name")}]
        return []

    mock_api.execute_long.side_effect = side
    mock_api.execute.side_effect = side
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)

    result = svc.userman_restore("discovered_1", tar, backup_root=str(tmp_path))

    assert result["success"] is True
    assert result["profiles_restored"] == 1
    assert result["users_restored"] == 1
    assert result["errors"] == []


def test_profile_fallback_on_field_rejection(svc, tmp_path, mock_api, monkeypatch):
    tar = _make_tar(tmp_path, [{"name": "p1", "shared-users": 2, "uptime": "1h"}], [])

    calls = {"profile_add": 0}

    def side(rk, command, **kwargs):
        if command.endswith("/print"):
            return []
        if command == "user-manager/profile/add":
            calls["profile_add"] += 1
            if calls["profile_add"] == 1:
                raise LibRouterosError("unknown parameter 'uptime'")
            return [{"name": kwargs.get("name")}]
        return []

    mock_api.execute_long.side_effect = side
    mock_api.execute.side_effect = side
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)

    result = svc.userman_restore("discovered_1", tar, backup_root=str(tmp_path))

    assert result["profiles_restored"] == 1
    assert result["errors"] == []
    fallback_call = mock_api.execute_long.call_args_list[1]
    assert "uptime" not in fallback_call.kwargs


def test_user_fallback_drops_caller_id_but_keeps_password(svc, tmp_path, mock_api, monkeypatch):
    # v6 rejects caller-id; the restore must fall back to name+password+profile
    # (preserving the password) and must NOT include caller-id.
    tar = _make_tar(
        tmp_path,
        [],
        [{"name": "u1", "password": "pw", "profile": "default", "caller-id": "AA:BB:CC:DD:EE:01"}],
    )

    calls = {"user_add": 0}

    def side(rk, command, **kwargs):
        if command.endswith("/print"):
            return []
        if command == "user-manager/user/add":
            calls["user_add"] += 1
            if calls["user_add"] == 1:
                raise LibRouterosError("unknown parameter 'caller-id'")
            return [{"name": kwargs.get("name")}]
        return []

    mock_api.execute_long.side_effect = side
    mock_api.execute.side_effect = side
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)

    result = svc.userman_restore("discovered_1", tar, backup_root=str(tmp_path))

    assert result["users_restored"] == 1
    assert result["errors"] == []
    fallback_call = mock_api.execute_long.call_args_list[1]
    assert "caller-id" not in fallback_call.kwargs
    assert fallback_call.kwargs.get("password") == "pw"


def test_persistent_failure_records_error(svc, tmp_path, mock_api, monkeypatch):
    tar = _make_tar(tmp_path, [{"name": "p1", "shared-users": 2}], [])

    def side(rk, command, **kwargs):
        if command.endswith("/print"):
            return []
        if command == "user-manager/profile/add":
            raise LibRouterosError("unknown parameter 'x'")
        return []

    mock_api.execute_long.side_effect = side
    mock_api.execute.side_effect = side
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)

    result = svc.userman_restore("discovered_1", tar, backup_root=str(tmp_path))

    assert result["profiles_restored"] == 0
    assert result["success"] is False
    assert len(result["errors"]) == 1


def test_skips_existing(svc, tmp_path, mock_api, monkeypatch):
    tar = _make_tar(tmp_path, [{"name": "p1"}], [{"name": "u1"}])

    def side(rk, command, **kwargs):
        if command == "user-manager/profile/print":
            return [{"name": "p1"}]
        if command == "user-manager/user/print":
            return [{"name": "u1"}]
        if command.endswith("/add"):
            return []
        return []

    mock_api.execute_long.side_effect = side
    mock_api.execute.side_effect = side
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)

    result = svc.userman_restore("discovered_1", tar, backup_root=str(tmp_path))

    assert result["profiles_restored"] == 0
    assert result["users_restored"] == 0
    assert result["skipped"]["profiles"] == 1
    assert result["skipped"]["users"] == 1


def test_missing_tar_returns_failure(svc, tmp_path, mock_api, monkeypatch):
    monkeypatch.setattr("core.backup.userman.mikrotik_api", mock_api)
    result = svc.userman_restore("discovered_1", str(tmp_path / "nope.tar"), backup_root=str(tmp_path))
    assert result["success"] is False


def test_user_add_args_includes_caller_id_when_present():
    svc = UserManagerBackupService()
    args = svc._user_add_args(
        "u1",
        {"name": "u1", "password": "pw", "profile": "default", "caller-id": "AA:BB:CC:DD:EE:01"},
    )
    assert args["caller-id"] == "AA:BB:CC:DD:EE:01"
    assert args["password"] == "pw"
    args2 = svc._user_add_args("u2", {"name": "u2", "profile": "default"})
    assert "caller-id" not in args2
