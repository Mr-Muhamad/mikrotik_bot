"""Tests for core.profile_sync."""

from unittest.mock import MagicMock

from core.profile_sync import ProfileSync, profile_sync


class TestProfileSync:
    def setup_method(self):
        self.sync = ProfileSync()
        self.router_key = "discovered_1"

    def test_get_profiles_returns_names(self):
        from core.profile_sync import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(
            return_value=[{"name": "1M"}, {"name": "2M"}, {"name": ""}, {}]
        )

        result = self.sync.get_userman_profiles(self.router_key)

        assert result == ["1M", "2M"]

    def test_get_profiles_v6_path(self):
        from core.profile_sync import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="tool/user-manager")
        mikrotik_api.execute = MagicMock(return_value=[{"name": "old-profile"}])

        result = self.sync.get_userman_profiles(self.router_key)

        assert result == ["old-profile"]
        args = mikrotik_api.execute.call_args[0]
        assert args[1] == "tool/user-manager/profile/print"

    def test_get_profiles_empty(self):
        from core.profile_sync import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(return_value="user-manager")
        mikrotik_api.execute = MagicMock(return_value=[])

        result = self.sync.get_userman_profiles(self.router_key)

        assert result == []

    def test_get_profiles_exception_returns_empty(self):
        from core.profile_sync import mikrotik_api

        mikrotik_api.get_userman_base_path = MagicMock(side_effect=Exception("net down"))

        result = self.sync.get_userman_profiles(self.router_key)

        assert result == []

    def test_singleton_instance(self):
        assert profile_sync is not None
        assert isinstance(profile_sync, ProfileSync)
