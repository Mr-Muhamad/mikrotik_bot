"""Tests for core.userman_manager.UserManager."""

from unittest.mock import MagicMock

from core.userman_manager import UserManager


class TestUserManagerCredentials:
    def setup_method(self):
        self.manager = UserManager()

    def test_generate_username_default_length(self):
        username = self.manager.generate_username()
        assert len(username) == 8
        assert username.isdigit()

    def test_generate_username_custom_length(self):
        username = self.manager.generate_username(12)
        assert len(username) == 12
        assert username.isdigit()

    def test_generate_password_default_length(self):
        password = self.manager.generate_password()
        assert len(password) == 8
        assert password.isdigit()

    def test_generate_password_custom_length(self):
        password = self.manager.generate_password(15)
        assert len(password) == 15


class TestUserManagerCreateCards:
    def setup_method(self):
        self.manager = UserManager()
        self.router_key = "discovered_1"

    def test_create_cards_type1_distinct_creds(self):
        from core.userman_manager import mikrotik_api

        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user/print"):
                return []
            if cmd.endswith("/user-profile/print"):
                return [{"user": kw.get("name") or kw.get("user"), "profile": "1M"}]
            return None

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        cards = self.manager.create_cards(self.router_key, 3, "type1", "1M")

        assert len(cards) == 3
        for card in cards:
            assert len(card["username"]) == 8
            assert len(card["password"]) == 8
        # 1 fetch existing users + 3 cards * (add + user-profile/add + verify) = 10
        assert mikrotik_api.execute.call_count == 10
        # v7 must link via the user-profile table, not user/set
        link_calls = [
            c
            for c in mikrotik_api.execute.call_args_list
            if c.args[1] == "user-manager/user-profile/add"
        ]
        assert len(link_calls) == 3
        assert link_calls[0].kwargs["user"] == cards[0]["username"]
        assert link_calls[0].kwargs["profile"] == "1M"

    def test_create_cards_type2_username_equals_password(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock()

        cards = self.manager.create_cards(self.router_key, 2, "type2", "1M")

        assert len(cards) == 2
        for card in cards:
            assert card["username"] == card["password"]

    def test_create_cards_type3_empty_password(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock()

        cards = self.manager.create_cards(self.router_key, 2, "type3", "1M")

        for card in cards:
            assert card["password"] == ""

    def test_create_cards_invalid_type_silently_skipped(self):
        cards = self.manager.create_cards(self.router_key, 1, "type99", "1M")
        assert cards == []

    def test_create_cards_continues_on_failure(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        # v7 create_cards now issues add + set per user; let the first card fail
        # and the remaining two fully succeed (4 successful calls).
        mikrotik_api.execute = MagicMock(side_effect=[Exception("boom"), None, None, None, None])

        cards = self.manager.create_cards(self.router_key, 3, "type1", "1M")

        assert len(cards) == 2

    def test_create_user_uses_v6_path(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="tool/user-manager")
        mikrotik_api.execute = MagicMock()

        self.manager._create_user(self.router_key, "u1", "p1", "1M")

        calls = mikrotik_api.execute.call_args_list
        # user/add must NOT carry profile on v6 (RouterOS rejects it there)
        add_call = calls[0]
        assert add_call.args[1] == "tool/user-manager/user/add"
        assert add_call.kwargs["name"] == "u1"
        assert add_call.kwargs["password"] == "p1"
        assert add_call.kwargs["shared-users"] == 1
        assert "profile" not in add_call.kwargs
        # profile is attached via the dedicated v6 activation command
        activate_call = calls[1]
        assert activate_call.args[1] == "tool/user-manager/user/create-and-activate-profile"
        assert activate_call.kwargs["profile"] == "1M"
        assert activate_call.kwargs["numbers"] == "u1"
        assert activate_call.kwargs["customer"] == "admin"

    def test_create_user_omits_empty_password(self):
        from core.userman_manager import mikrotik_api

        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        result = self.manager._create_user(self.router_key, "u1", "", "1M")

        calls = mikrotik_api.execute.call_args_list
        # add without password and without profile
        assert "password" not in calls[0].kwargs
        assert "profile" not in calls[0].kwargs
        # profile linked afterwards via the user-profile table on v7
        assert calls[1].args[1] == "user-manager/user-profile/add"
        assert calls[1].kwargs["user"] == "u1"
        assert calls[1].kwargs["profile"] == "1M"
        # verification read-back must NOT pass a rejected user= filter
        verify_call = calls[2]
        assert verify_call.args[1] == "user-manager/user-profile/print"
        assert "user" not in verify_call.kwargs
        # add + user-profile/add + verify read-back
        assert mikrotik_api.execute.call_count == 3
        # link reported as successful because the read-back matched
        assert result["profile_linked"] is True

    def test_create_user_v6_activation_failure_still_creates_user(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="tool/user-manager")
        # user/add succeeds, profile activation fails
        mikrotik_api.execute = MagicMock(side_effect=[None, Exception("no such profile")])

        # must not raise; the user row already exists
        self.manager._create_user(self.router_key, "u1", "p1", "1M")

        assert mikrotik_api.execute.call_count == 2

    def test_create_user_v7_links_profile_via_user_profile_table(self):
        from core.userman_manager import mikrotik_api

        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        result = self.manager._create_user(self.router_key, "u1", "p1", "1M")

        calls = mikrotik_api.execute.call_args_list
        # add never carries the profile; it is linked via the user-profile table
        assert calls[0].args[1] == "user-manager/user/add"
        assert "profile" not in calls[0].kwargs
        assert calls[1].args[1] == "user-manager/user-profile/add"
        assert calls[1].kwargs["user"] == "u1"
        assert calls[1].kwargs["profile"] == "1M"
        # link is verified by a read-back; the print must NOT use a user= filter
        verify_call = calls[2]
        assert verify_call.args[1] == "user-manager/user-profile/print"
        assert "user" not in verify_call.kwargs
        assert mikrotik_api.execute.call_count == 3
        # result reports the link status so the caller can surface failures
        assert result["profile_linked"] is True
        assert result["link_error"] is None

    def test_create_user_v7_profile_link_failure_is_reported(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        # add succeeds, but the profile link (user-profile/add) fails
        mikrotik_api.execute = MagicMock(side_effect=[None, Exception("no such profile")])

        # must not raise; the user row already exists, and the failure is reported
        result = self.manager._create_user(self.router_key, "u1", "p1", "1M")

        assert mikrotik_api.execute.call_count == 2
        assert result["profile_linked"] is False
        assert "no such profile" in (result["link_error"] or "")

    def test_create_user_v7_verify_confirms_link(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")

        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user-profile/print"):
                return [{"user": "u1", "profile": "1M"}]
            return None

        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        result = self.manager._create_user(self.router_key, "u1", "p1", "1M")

        assert result["profile_linked"] is True
        assert result["link_error"] is None

    def test_verify_profile_link_matches_numeric_int_user_field(self):
        from core.userman_manager import mikrotik_api

        # RouterOS returns numeric usernames as ints in the user-profile table,
        # so the read-back must coerce both sides to str before comparing.
        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user-profile/print"):
                return [{"user": 5680538, "profile": "1M"}]
            return None

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        result = self.manager._create_user(self.router_key, "5680538", "p1", "1M")

        assert result["profile_linked"] is True
        assert result["link_error"] is None


class TestUserManagerList:
    def setup_method(self):
        self.manager = UserManager()
        self.router_key = "discovered_1"

    def test_list_users_respects_limit(self):
        from core.userman_manager import mikrotik_api

        users = [{"name": f"u{i}"} for i in range(100)]
        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(return_value=users)

        result = self.manager.list_users(self.router_key, limit=10)

        assert len(result) == 10

    def test_list_users_default_limit(self):
        from core.userman_manager import mikrotik_api

        users = [{"name": f"u{i}"} for i in range(60)]
        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(return_value=users)

        result = self.manager.list_users(self.router_key)

        assert len(result) == 50

    def test_list_users_uses_v6_path(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="tool/user-manager")
        mikrotik_api.execute = MagicMock(return_value=[])

        self.manager.list_users(self.router_key)

        assert "tool/user-manager/user/print" in mikrotik_api.execute.call_args[0]


class TestUserManagerFormatCard:
    def setup_method(self):
        self.manager = UserManager()

    def test_format_card_with_password(self):
        card = {"username": "12345", "password": "67890"}
        result = self.manager.format_card(card, 0)
        assert "كارت #1" in result
        assert "12345" in result
        assert "67890" in result

    def test_format_card_empty_password(self):
        card = {"username": "u1", "password": ""}
        result = self.manager.format_card(card, 4)
        assert "كارت #5" in result
        assert "فارغة" in result


class TestUserManagerCreateCardsCallerId:
    def setup_method(self):
        self.manager = UserManager()
        self.router_key = "discovered_1"

    def test_create_cards_no_longer_accepts_caller_id(self):
        from core.userman_manager import mikrotik_api

        def fake_execute(rk, cmd, **kw):
            if cmd.endswith("/user-profile/print"):
                return [{"user": kw.get("name") or kw.get("user"), "profile": "1M"}]
            return None

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(side_effect=fake_execute)

        cards = self.manager.create_cards(self.router_key, 2, "type2", "1M")

        assert len(cards) == 2
        for card in cards:
            assert "caller_id" not in card
        add_calls = [
            c for c in mikrotik_api.execute.call_args_list if c.args[1] == "user-manager/user/add"
        ]
        assert len(add_calls) == 2
        assert "caller-id" not in add_calls[0].kwargs

    def test_set_user_caller_id_sets_caller_id(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock()
        self.manager._get_user_id = MagicMock(return_value="*123")

        self.manager.set_user_caller_id(self.router_key, "testuser", "AA:BB:CC:DD:EE:FF")

        set_calls = [
            c for c in mikrotik_api.execute.call_args_list if c.args[1] == "user-manager/user/set"
        ]
        assert len(set_calls) == 1
        assert set_calls[0].kwargs["caller-id"] == "AA:BB:CC:DD:EE:FF"

    def test_create_user_omits_empty_caller_id(self):
        from core.userman_manager import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock()

        result = self.manager._create_user(self.router_key, "u1", "p1", "")

        add_call = mikrotik_api.execute.call_args_list[0]
        assert "caller-id" not in add_call.kwargs
        assert "caller_id" not in result
