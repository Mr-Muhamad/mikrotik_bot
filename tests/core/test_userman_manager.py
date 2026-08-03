"""Comprehensive tests for core.userman_manager.UserManager."""

from typing import cast
from unittest.mock import MagicMock

import pytest

from core.card_models import CardSystem
from core.userman_manager import UserManager

RK = "discovered_1"
V7 = "user-manager"
V6 = "tool/user-manager"


# ── helpers ──────────────────────────────────────────────────────────


def _make_manager(api: MagicMock | None = None) -> tuple[UserManager, MagicMock]:
    if api is None:
        api = MagicMock()
    return UserManager(api=api), api


def _v7_api(api: MagicMock) -> MagicMock:
    api.get_userman_base_path.return_value = "user-manager"
    return api


def _v6_api(api: MagicMock) -> MagicMock:
    api.get_userman_base_path.return_value = "tool/user-manager"
    return api


# ═══════════════════════════════════════════════════════════════════════
# 1. _api property
# ═══════════════════════════════════════════════════════════════════════


class TestApiProperty:
    def test_returns_injected_api(self):
        mock = MagicMock()
        mgr = UserManager(api=mock)
        assert mgr._api is mock  # type: ignore[reportPrivateUsage]

    def test_falls_back_to_singleton(self):
        mgr = UserManager(api=None)
        from core.mikrotik_api import mikrotik_api

        assert mgr._api is mikrotik_api  # type: ignore[reportPrivateUsage]


# ═══════════════════════════════════════════════════════════════════════
# 2. _get_all_users_cached
# ═══════════════════════════════════════════════════════════════════════


class TestGetAllUsersCached:
    def test_caches_second_call(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1"}]

        r1 = mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]
        r2 = mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]

        assert r1 == r2 == [{"name": "u1"}]
        assert api.execute.call_count == 1

    def test_different_router_keys_not_shared(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1"}]

        mgr._get_all_users_cached("rk_a", V7)  # type: ignore[reportPrivateUsage]
        mgr._get_all_users_cached("rk_b", V7)  # type: ignore[reportPrivateUsage]

        assert api.execute.call_count == 2


# ═══════════════════════════════════════════════════════════════════════
# 3. invalidate_users_cache
# ═══════════════════════════════════════════════════════════════════════


class TestInvalidateCache:
    def test_invalidate_refetches(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "v1"}]

        mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]
        mgr.invalidate_users_cache(RK)
        api.execute.return_value = [{"name": "v2"}]

        result = mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]
        assert result == [{"name": "v2"}]
        assert api.execute.call_count == 2


# ═══════════════════════════════════════════════════════════════════════
# 4. create_cards – full matrix
# ═══════════════════════════════════════════════════════════════════════


class TestCreateCards:
    def _fake_execute(self, api, *, verify_user: str = "u", profile: str = "1M"):  # type: ignore[reportMissingParameterType]
        """Side-effect that handles existing-users print, add, link, verify."""

        def inner(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user/print") and ".proplist" in kw:
                proplist = kw[".proplist"]
                if "name" in proplist and ".id" not in proplist:
                    return []
                if "user" in proplist and ".id" not in proplist:
                    return []
                return []
            if cmd.endswith("/user-profile/print"):
                u = kw.get("user") or verify_user
                return [{"user": u, "profile": profile}]
            return None

        return inner

    def test_type1_different_credentials(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = self._fake_execute(api)

        cards = mgr.create_cards(RK, 3, "type1", "1M")
        assert len(cards) == 3
        for c in cards:
            username = c["username"]
            password = c["password"]
            assert isinstance(username, str)
            assert isinstance(password, str)
            assert len(username) == 8
            assert len(password) == 8
            assert username != password

    def test_type2_same_credentials(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = self._fake_execute(api)

        cards = mgr.create_cards(RK, 2, "type2", "1M")
        for c in cards:
            assert c["username"] == c["password"]

    def test_type3_empty_password(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = self._fake_execute(api)

        cards = mgr.create_cards(RK, 2, "type3", "1M")
        for c in cards:
            assert c["password"] == ""

    def test_invalid_type_string_returns_empty(self):
        mgr, _ = _make_manager()
        assert mgr.create_cards(RK, 1, "type99", "1M") == []

    def test_invalid_card_system_enum_returns_empty(self):
        mgr, _ = _make_manager()
        assert mgr.create_cards(RK, 1, "INVALID", "1M") == []

    def test_non_card_system_type_returns_empty(self):
        mgr, _ = _make_manager()
        assert mgr.create_cards(RK, 1, cast(CardSystem | str | None, 12345), "1M") == []

    def test_existing_users_fetch_failure_still_proceeds(self):
        mgr, api = _make_manager()
        _v7_api(api)

        call_count = [0]

        def side_effect(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            call_count[0] += 1
            if cmd.endswith("/user/print") and "name,username" in kw.get(
                ".proplist", ""
            ):
                raise Exception("network error")
            if cmd.endswith("/user-print") and ".proplist" in kw:
                return []
            if cmd.endswith("/user/print") and ".proplist" in kw:
                proplist = kw[".proplist"]
                if ".id" in proplist:
                    return []
                return []
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u", "profile": "1M"}]
            return None

        api.execute.side_effect = side_effect
        cards = mgr.create_cards(RK, 1, "type1", "1M")
        assert len(cards) == 1

    def test_continues_after_card_failure(self):
        mgr, api = _make_manager()
        _v7_api(api)

        call_idx = [0]

        def side_effect(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            call_idx[0] += 1
            if cmd.endswith("/user/print") and ".proplist" in kw:
                proplist = kw[".proplist"]
                if "name" in proplist and ".id" not in proplist:
                    return []
                return []
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u", "profile": "1M"}]
            if call_idx[0] == 2:
                raise Exception("boom")
            return None

        api.execute.side_effect = side_effect
        cards = mgr.create_cards(RK, 2, "type1", "1M")
        assert len(cards) == 1

    def test_with_prefix(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = self._fake_execute(api)

        cards = mgr.create_cards(RK, 1, "type1", "1M", prefix="PRE")
        username = cards[0]["username"]
        assert isinstance(username, str)
        assert username.startswith("PRE")

    def test_v6_create_cards(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = self._fake_execute(api)

        cards = mgr.create_cards(RK, 1, "type1", "1M")
        assert len(cards) == 1
        add_calls = [c for c in api.execute.call_args_list if "/user/add" in c.args[1]]
        assert add_calls[0].kwargs["shared-users"] == "1"

    def test_with_caller_id(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = self._fake_execute(api)

        mgr.create_cards(RK, 1, "type1", "1M", caller_id="AA:BB")
        add_calls = [c for c in api.execute.call_args_list if "/user/add" in c.args[1]]
        assert add_calls[0].kwargs["caller-id"] == "AA:BB"


# ═══════════════════════════════════════════════════════════════════════
# 5. _create_user
# ═══════════════════════════════════════════════════════════════════════


class TestCreateUser:
    def test_v7_with_profile(self):
        mgr, api = _make_manager()
        _v7_api(api)

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        api.execute.side_effect = side
        result = mgr._create_user(RK, "u1", "p1", "1M")  # type: ignore[reportPrivateUsage]

        calls = api.execute.call_args_list
        assert calls[0].args[1] == f"{V7}/user/add"
        assert calls[0].kwargs["name"] == "u1"
        assert "profile" not in calls[0].kwargs
        assert calls[1].args[1] == f"{V7}/user-profile/add"
        assert result["profile_linked"] is True

    def test_v7_empty_profile_no_linking(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        result = mgr._create_user(RK, "u1", "p1", "")  # type: ignore[reportPrivateUsage]

        assert api.execute.call_count == 1
        assert result["profile_linked"] is False
        assert result["link_error"] is None

    def test_v6_with_profile(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M")  # type: ignore[reportPrivateUsage]

        calls = api.execute.call_args_list
        assert calls[0].args[1] == f"{V6}/user/add"
        assert calls[0].kwargs["shared-users"] == "1"
        assert calls[1].args[1] == f"{V6}/user/create-and-activate-profile"

    def test_v6_empty_password(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = None

        result = mgr._create_user(RK, "u1", "", "1M")  # type: ignore[reportPrivateUsage]
        add_call = api.execute.call_args_list[0]
        assert "password" not in add_call.kwargs
        assert result["password"] == ""

    def test_v7_comment_sanitized(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M", comment="  test  ")  # type: ignore[reportPrivateUsage]

        add_call = api.execute.call_args_list[0]
        assert "comment" in add_call.kwargs

    def test_v7_with_caller_id(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M", caller_id="AA:BB")  # type: ignore[reportPrivateUsage]
        add_call = api.execute.call_args_list[0]
        assert add_call.kwargs["caller-id"] == "AA:BB"

    def test_v7_empty_comment_not_added(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M", comment="")  # type: ignore[reportPrivateUsage]
        add_call = api.execute.call_args_list[0]
        assert "comment" not in add_call.kwargs

    def test_v6_empty_caller_id_not_added(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M", caller_id="")  # type: ignore[reportPrivateUsage]
        add_call = api.execute.call_args_list[0]
        assert "caller-id" not in add_call.kwargs


# ═══════════════════════════════════════════════════════════════════════
# 6 & 7. _attach_v7_profile / _attach_v6_profile
# ═══════════════════════════════════════════════════════════════════════


class TestAttachV7Profile:
    def test_success(self):
        mgr, api = _make_manager()
        _v7_api(api)

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        api.execute.side_effect = side
        linked, err = mgr._attach_v7_profile(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert linked is True
        assert err is None

    def test_api_exception(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = Exception("connection lost")

        linked, err = mgr._attach_v7_profile(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert linked is False
        assert err is not None
        assert "connection lost" in err


class TestAttachV6Profile:
    def test_success(self):
        mgr, api = _make_manager()
        _v6_api(api)

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        api.execute.side_effect = side
        linked, err = mgr._attach_v6_profile(RK, V6, "u1", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert linked is True

    def test_api_exception(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = Exception("fail")

        linked, err = mgr._attach_v6_profile(RK, V6, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert linked is False
        assert err is not None
        assert "fail" in err


# ═══════════════════════════════════════════════════════════════════════
# 8. _verify_profile_link
# ═══════════════════════════════════════════════════════════════════════


class TestVerifyProfileLink:
    def test_matching_user_field(self):
        mgr, api = _make_manager()
        api.execute.return_value = [{"user": "u1", "profile": "1M"}]
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert ok is True
        assert err is None

    def test_matching_username_field(self):
        mgr, api = _make_manager()
        api.execute.return_value = [{"username": "u1", "profile": "1M"}]
        ok, err = mgr._verify_profile_link(RK, V6, "u1", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert ok is True

    def test_no_matching_profile(self):
        mgr, api = _make_manager()
        api.execute.return_value = [{"user": "u1", "profile": "2M"}]
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert ok is False
        assert err is not None
        assert "not found" in err

    def test_empty_rows(self):
        mgr, api = _make_manager()
        api.execute.return_value = []
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert ok is False

    def test_none_rows(self):
        mgr, api = _make_manager()
        api.execute.return_value = None
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert ok is False

    def test_numeric_user_id_coercion(self):
        mgr, api = _make_manager()
        api.execute.return_value = [{"user": 5680538, "profile": "1M"}]
        ok, err = mgr._verify_profile_link(RK, V7, "5680538", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert ok is True

    def test_api_exception_during_verify(self):
        mgr, api = _make_manager()
        api.execute.side_effect = Exception("timeout")
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert ok is False
        assert err is not None
        assert "verify failed" in err

    def test_user_not_in_profile_table(self):
        mgr, api = _make_manager()
        api.execute.return_value = [{"user": "other", "profile": "1M"}]
        ok, err = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportUnusedVariable, reportPrivateUsage]
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════
# 9. _get_user_id
# ═══════════════════════════════════════════════════════════════════════


class TestGetUserId:
    def test_v7_resolves_via_name(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{".id": "*1", "name": "u1"}]

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid == "*1"

    def test_v6_resolves_via_username(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{".id": "*2", "username": "u1"}]

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid == "*2"

    def test_filter_fails_fallback_to_cache(self):
        mgr, api = _make_manager()
        _v7_api(api)

        call_count = [0]

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("filter unsupported")
            return [{".id": "*5", "name": "u1"}]

        api.execute.side_effect = side
        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid == "*5"

    def test_not_found(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{".id": "*1", "name": "other"}]

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid is None

    def test_both_attempts_fail(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = Exception("network error")

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid is None


# ═══════════════════════════════════════════════════════════════════════
# 10. set_user_caller_id
# ═══════════════════════════════════════════════════════════════════════


class TestSetUserCallerId:
    def test_sets_caller_id(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{".id": "*1", "name": "u1"}]

        mgr.set_user_caller_id(RK, "u1", "AA:BB:CC")

        set_calls = [c for c in api.execute.call_args_list if "/user/set" in c.args[1]]
        assert len(set_calls) == 1
        assert set_calls[0].kwargs["caller-id"] == "AA:BB:CC"
        assert set_calls[0].kwargs[".id"] == "*1"

    def test_empty_caller_id_noop(self):
        mgr, api = _make_manager()
        _v7_api(api)

        mgr.set_user_caller_id(RK, "u1", "")
        api.execute.assert_not_called()

    def test_user_not_found(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        mgr.set_user_caller_id(RK, "missing", "AA:BB")
        set_calls = [c for c in api.execute.call_args_list if "/user/set" in c.args[1]]
        assert len(set_calls) == 0


# ═══════════════════════════════════════════════════════════════════════
# 11. list_users
# ═══════════════════════════════════════════════════════════════════════


class TestListUsers:
    def test_v7_normalization(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1"}, {"name": "u2"}]

        result = mgr.list_users(RK, limit=10)
        assert len(result) == 2
        assert all("name" in u for u in result)

    def test_v6_normalizes_username_to_name(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{"username": "u1"}]

        result = mgr.list_users(RK)
        assert result[0]["name"] == "u1"

    def test_limit_zero(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1"}]

        result = mgr.list_users(RK, limit=0)
        assert result == []

    def test_empty_response(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        result = mgr.list_users(RK)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# 12. search_users
# ═══════════════════════════════════════════════════════════════════════


class TestSearchUsers:
    def test_v7_match(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "alice"}, {"name": "bob"}]

        result = mgr.search_users(RK, "ali")
        assert len(result) == 1
        assert result[0]["name"] == "alice"

    def test_v6_match(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{"username": "alice"}, {"username": "bob"}]

        result = mgr.search_users(RK, "ali")
        assert len(result) == 1

    def test_no_match(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "alice"}]

        result = mgr.search_users(RK, "zzz")
        assert result == []

    def test_case_insensitive(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "Alice"}]

        result = mgr.search_users(RK, "alice")
        assert len(result) == 1

    def test_v6_normalizes_to_name(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{"username": "u1", ".id": "*1"}]

        result = mgr.search_users(RK, "u1")
        assert result[0]["name"] == "u1"

    def test_empty_search_term(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1"}]

        result = mgr.search_users(RK, "")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════
# 13. get_user
# ═══════════════════════════════════════════════════════════════════════


class TestGetUser:
    def test_found(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [{".id": "*1", "name": "u1", "disabled": "false"}],
        ]

        user = mgr.get_user(RK, "u1")
        assert user is not None
        assert user["name"] == "u1"

    def test_not_found(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        user = mgr.get_user(RK, "missing")
        assert user is None

    def test_v6_normalizes_username_to_name(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "username": "u1"}],
            [{".id": "*1", "username": "u1"}],
        ]

        user = mgr.get_user(RK, "u1")
        assert user is not None
        assert user["name"] == "u1"


# ═══════════════════════════════════════════════════════════════════════
# 14. add_profile_to_user
# ═══════════════════════════════════════════════════════════════════════


class TestAddProfileToUser:
    def test_v7_adds_profile(self):
        mgr, api = _make_manager()
        _v7_api(api)

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "2M"}]
            return None

        api.execute.side_effect = side
        linked, err = mgr.add_profile_to_user(RK, "u1", "2M")  # type: ignore[reportUnusedVariable]
        assert linked is True

    def test_v6_adds_profile(self):
        mgr, api = _make_manager()
        _v6_api(api)

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user-profile/print"):
                return [{"username": "u1", "profile": "2M"}]
            return None

        api.execute.side_effect = side
        linked, err = mgr.add_profile_to_user(RK, "u1", "2M")  # type: ignore[reportUnusedVariable]
        assert linked is True


# ═══════════════════════════════════════════════════════════════════════
# 15. delete_user
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteUser:
    def test_deletes(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [],
        ]

        mgr.delete_user(RK, "u1")
        remove_calls = [c for c in api.execute.call_args_list if "/user/remove" in c.args[1]]
        assert len(remove_calls) == 1
        assert remove_calls[0].kwargs[".id"] == "*1"

    def test_user_not_found_raises(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError, match="not found"):
            mgr.delete_user(RK, "missing")


# ═══════════════════════════════════════════════════════════════════════
# 16. enable_user
# ═══════════════════════════════════════════════════════════════════════


class TestEnableUser:
    def test_enables(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [],
        ]

        mgr.enable_user(RK, "u1")
        enable_calls = [c for c in api.execute.call_args_list if "/user/enable" in c.args[1]]
        assert len(enable_calls) == 1
        assert enable_calls[0].kwargs[".id"] == "*1"

    def test_user_not_found_raises(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError, match="not found"):
            mgr.enable_user(RK, "missing")


# ═══════════════════════════════════════════════════════════════════════
# 17. disable_user
# ═══════════════════════════════════════════════════════════════════════


class TestDisableUser:
    def test_disables(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [],
        ]

        mgr.disable_user(RK, "u1")
        disable_calls = [c for c in api.execute.call_args_list if "/user/disable" in c.args[1]]
        assert len(disable_calls) == 1

    def test_user_not_found_raises(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError, match="not found"):
            mgr.disable_user(RK, "missing")


# ═══════════════════════════════════════════════════════════════════════
# 18. reset_user_counters
# ═══════════════════════════════════════════════════════════════════════


class TestResetUserCounters:
    def test_v7_uses_reset_counters(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [],
        ]

        mgr.reset_user_counters(RK, "u1")
        rc_calls = [
            c for c in api.execute.call_args_list if "/user/reset-counters" in c.args[1]
        ]
        assert len(rc_calls) == 1
        assert rc_calls[0].kwargs[".id"] == "*1"

    def test_v6_uses_clear_profiles(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "username": "u1"}],
            [],
        ]

        mgr.reset_user_counters(RK, "u1")
        cp_calls = [
            c for c in api.execute.call_args_list if "/user/clear-profiles" in c.args[1]
        ]
        assert len(cp_calls) == 1

    def test_user_not_found_raises(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError, match="not found"):
            mgr.reset_user_counters(RK, "missing")


# ═══════════════════════════════════════════════════════════════════════
# 19. get_active_sessions
# ═══════════════════════════════════════════════════════════════════════


class TestGetActiveSessions:
    def test_primary_filter_works(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"user": "u1", "active": "true"}]

        result = mgr.get_active_sessions(RK)
        assert len(result) == 1
        assert result[0]["user"] == "u1"

    def test_fallback_when_primary_empty(self):
        mgr, api = _make_manager()
        _v7_api(api)

        call_idx = [0]

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            call_idx[0] += 1
            if call_idx[0] == 1:
                return []
            return [
                {"user": "u1", "active": "true"},
                {"user": "u2", "active": "false"},
            ]

        api.execute.side_effect = side
        result = mgr.get_active_sessions(RK)
        assert len(result) == 1
        assert result[0]["user"] == "u1"

    def test_v6_normalizes_username_to_user(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{"username": "u1", "active": "true"}]

        result = mgr.get_active_sessions(RK)
        assert result[0]["user"] == "u1"

    def test_empty_fallback_all_inactive(self):
        mgr, api = _make_manager()
        _v7_api(api)

        call_idx = [0]

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            call_idx[0] += 1
            if call_idx[0] == 1:
                return []
            return [{"user": "u1", "active": "false"}]

        api.execute.side_effect = side
        result = mgr.get_active_sessions(RK)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# 20. terminate_session
# ═══════════════════════════════════════════════════════════════════════


class TestTerminateSession:
    def test_v7_terminates(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        mgr.terminate_session(RK, "*99")
        remove_calls = [
            c for c in api.execute.call_args_list if "/session/remove" in c.args[1]
        ]
        assert len(remove_calls) == 1
        assert remove_calls[0].kwargs["numbers"] == "*99"

    def test_v6_terminates(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = None

        mgr.terminate_session(RK, "*42")
        remove_calls = [
            c for c in api.execute.call_args_list if "/session/remove" in c.args[1]
        ]
        assert len(remove_calls) == 1
        assert remove_calls[0].kwargs["numbers"] == "*42"


# ═══════════════════════════════════════════════════════════════════════
# 21. format_card
# ═══════════════════════════════════════════════════════════════════════


class TestFormatCard:
    def test_with_password(self):
        mgr, _ = _make_manager()
        result = mgr.format_card({"username": "12345", "password": "67890"}, 0)
        assert "12345" in result
        assert "67890" in result
        assert "فارغة" not in result

    def test_empty_password(self):
        mgr, _ = _make_manager()
        result = mgr.format_card({"username": "u1", "password": ""}, 4)
        assert "فارغة" in result
        assert "كارت #5" in result

    def test_index_offset(self):
        mgr, _ = _make_manager()
        result = mgr.format_card({"username": "x", "password": "y"}, 9)
        assert "كارت #10" in result


# ═══════════════════════════════════════════════════════════════════════
# Additional edge-case / integration tests
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_generate_username_length(self):
        mgr, _ = _make_manager()
        for length in [1, 4, 16]:
            u = mgr.generate_username(length)
            assert len(u) == length
            assert u.isdigit()

    def test_generate_password_length(self):
        mgr, _ = _make_manager()
        for length in [1, 4, 16]:
            p = mgr.generate_password(length)
            assert len(p) == length
            assert p.isdigit()

    def test_create_cards_zero_count(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        cards = mgr.create_cards(RK, 0, "type1", "1M")
        assert cards == []

    def test_list_users_preserves_extra_keys(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "u1", "disabled": "false", "comment": "test"}]

        result = mgr.list_users(RK)
        assert result[0]["disabled"] == "false"
        assert result[0]["comment"] == "test"

    def test_search_users_preserves_extra_keys(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{"name": "alice", "disabled": "true"}]

        result = mgr.search_users(RK, "alice")
        assert result[0]["disabled"] == "true"

    def test_get_user_extra_keys(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [{".id": "*1", "name": "u1", "comment": "c", "disabled": "false"}],
        ]

        user = mgr.get_user(RK, "u1")
        assert user is not None
        assert user["comment"] == "c"
        assert user["disabled"] == "false"

    def test_v6_list_users_all_paths(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [
            {"username": "a", ".id": "*1"},
            {"username": "b", ".id": "*2"},
        ]

        result = mgr.list_users(RK, limit=1)
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_invalidate_both_caches(self):
        mgr, api = _make_manager()
        _v7_api(api)

        users_data = [{"name": "u1"}]
        sessions_data = [{"user": "u1", "active": "true"}]
        api.execute.side_effect = [users_data, sessions_data, [], []]

        mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]
        mgr.get_active_sessions(RK)
        assert api.execute.call_count == 2

        mgr.invalidate_users_cache(RK)

        api.execute.side_effect = [[{"name": "u2"}], []]
        result = mgr._get_all_users_cached(RK, V7)  # type: ignore[reportPrivateUsage]
        assert result == [{"name": "u2"}]

    def test_get_user_id_v6_field_is_username(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = [{".id": "*3", "username": "u1"}]

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid == "*3"
        call_kwargs = api.execute.call_args_list[0].kwargs
        assert "?username" in call_kwargs

    def test_get_user_id_v7_field_is_name(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = [{".id": "*3", "name": "u1"}]

        uid = mgr._get_user_id(RK, "u1")  # type: ignore[reportPrivateUsage]
        assert uid == "*3"
        call_kwargs = api.execute.call_args_list[0].kwargs
        assert "?name" in call_kwargs

    def test_set_user_caller_id_v6(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = [[{".id": "*1", "username": "u1"}], None]

        mgr.set_user_caller_id(RK, "u1", "FF:FF")
        set_calls = [c for c in api.execute.call_args_list if "/user/set" in c.args[1]]
        assert len(set_calls) == 1
        assert set_calls[0].kwargs["caller-id"] == "FF:FF"

    def test_create_cards_dedup_skips_existing(self):
        mgr, api = _make_manager()
        _v7_api(api)

        existing_names = ["u"]

        def side(rk, cmd, **kw):  # type: ignore[reportMissingParameterType]
            if cmd.endswith("/user/print"):
                proplist = kw.get(".proplist", "")
                if ".id" not in proplist:
                    return [{"name": n} for n in existing_names]
                return []
            if cmd.endswith("/user-profile/print"):
                return []
            return None

        api.execute.side_effect = side

        cards = mgr.create_cards(RK, 1, "type1", "1M")
        assert len(cards) == 1

    def test_add_profile_to_user_v7_failure(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = Exception("timeout")

        linked, err = mgr.add_profile_to_user(RK, "u1", "2M")
        assert linked is False
        assert err is not None
        assert "timeout" in err

    def test_add_profile_to_user_v6_failure(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.side_effect = Exception("timeout")

        linked, err = mgr.add_profile_to_user(RK, "u1", "2M")
        assert linked is False
        assert err is not None
        assert "timeout" in err

    def test_get_user_returns_none_when_print_empty(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [
            [{".id": "*1", "name": "u1"}],
            [],
        ]

        user = mgr.get_user(RK, "u1")
        assert user is None

    def test_delete_user_not_found_not_called(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError):
            mgr.delete_user(RK, "x")
        remove_calls = [c for c in api.execute.call_args_list if "/user/remove" in c.args[1]]
        assert len(remove_calls) == 0

    def test_enable_user_not_found_not_called(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError):
            mgr.enable_user(RK, "x")
        enable_calls = [c for c in api.execute.call_args_list if "/user/enable" in c.args[1]]
        assert len(enable_calls) == 0

    def test_disable_user_not_found_not_called(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError):
            mgr.disable_user(RK, "x")
        disable_calls = [c for c in api.execute.call_args_list if "/user/disable" in c.args[1]]
        assert len(disable_calls) == 0

    def test_reset_counters_not_found_not_called(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = []

        with pytest.raises(ValueError):
            mgr.reset_user_counters(RK, "x")
        rc_calls = [
            c for c in api.execute.call_args_list if "/user/reset-counters" in c.args[1]
        ]
        assert len(rc_calls) == 0

    def test_verify_profile_link_multiple_rows(self):
        mgr, api = _make_manager()
        api.execute.return_value = [
            {"user": "other", "profile": "1M"},
            {"user": "u1", "profile": "2M"},
            {"user": "u1", "profile": "1M"},
        ]
        ok, _ = mgr._verify_profile_link(RK, V7, "u1", "1M")  # type: ignore[reportPrivateUsage]
        assert ok is True

    def test_create_user_v7_comment_with_prefix(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.return_value = None

        mgr._create_user(RK, "u1", "p1", "1M", comment="test_batch_001")  # type: ignore[reportPrivateUsage]
        add_call = api.execute.call_args_list[0]
        assert "comment" in add_call.kwargs

    def test_get_active_sessions_both_empty(self):
        mgr, api = _make_manager()
        _v7_api(api)
        api.execute.side_effect = [[], []]

        result = mgr.get_active_sessions(RK)
        assert result == []

    def test_terminate_session_v6_vs_v7_path(self):
        mgr, api = _make_manager()
        _v6_api(api)
        api.execute.return_value = None
        mgr.terminate_session(RK, "*1")
        v6_cmd = api.execute.call_args_list[0].args[1]
        assert v6_cmd.startswith("tool/")

        mgr2, api2 = _make_manager()
        _v7_api(api2)
        api2.execute.return_value = None
        mgr2.terminate_session(RK, "*1")
        v7_cmd = api2.execute.call_args_list[0].args[1]
        assert not v7_cmd.startswith("tool/")
