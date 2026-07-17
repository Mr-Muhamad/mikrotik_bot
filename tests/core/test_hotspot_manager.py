"""Unit tests for HotspotManager using the in-memory MikrotikAPIMock."""

import pytest
from unittest.mock import MagicMock

from core.hotspot_manager import hotspot_manager
from core.card_models import CardSystem, CardData


@pytest.mark.usefixtures("mock_mikrotik_api")
class TestHotspotManager:
    """All tests use mock_mikrotik_api which patches the singleton."""

    ROUTER_KEY = "discovered_1"

    def test_add_user_minimal(self, mock_mikrotik_api):
        result = hotspot_manager.add_user(
            self.ROUTER_KEY, name="newuser", password="pass",
            profile="default",
        )
        assert isinstance(result, list)

    def test_add_user_with_all_options(self, mock_mikrotik_api):
        result = hotspot_manager.add_user(
            self.ROUTER_KEY, name="fulluser", password="pass",
            profile="vip", bytes_total="1000000000",
            uptime="1d", comment="test card",
        )
        assert isinstance(result, list)

    def test_delete_existing_user(self, mock_mikrotik_api):
        result = hotspot_manager.delete_user(self.ROUTER_KEY, "*1")
        assert isinstance(result, list)
        user = hotspot_manager.get_user(self.ROUTER_KEY, "*1")
        assert user is None

    def test_delete_nonexistent_user(self, mock_mikrotik_api):
        result = hotspot_manager.delete_user(self.ROUTER_KEY, "*999")
        assert isinstance(result, list)

    def test_search_users_by_name(self, mock_mikrotik_api):
        results = hotspot_manager.search_users(self.ROUTER_KEY, "testuser1")
        assert len(results) >= 1
        assert any(u.get("name") == "testuser1" for u in results)

    def test_search_users_by_comment(self, mock_mikrotik_api):
        results = hotspot_manager.search_users(self.ROUTER_KEY, "vip")
        assert len(results) >= 1

    def test_search_users_no_results(self, mock_mikrotik_api):
        results = hotspot_manager.search_users(self.ROUTER_KEY, "zzz_no_match")
        assert len(results) == 0

    def test_get_existing_user(self, mock_mikrotik_api):
        user = hotspot_manager.get_user(self.ROUTER_KEY, "*1")
        assert user is not None
        assert user.get("name") == "testuser1"

    def test_get_nonexistent_user(self, mock_mikrotik_api):
        user = hotspot_manager.get_user(self.ROUTER_KEY, "*999")
        assert user is None

    def test_list_users(self, mock_mikrotik_api):
        users = hotspot_manager.list_users(self.ROUTER_KEY, limit=10)
        assert len(users) >= 1

    def test_get_profiles(self, mock_mikrotik_api):
        profiles = hotspot_manager.get_profiles(self.ROUTER_KEY)
        assert len(profiles) >= 1

    def test_search_hosts_by_ip(self, mock_mikrotik_api):
        hosts = hotspot_manager.search_hosts(self.ROUTER_KEY, "192.168.88.10")
        assert len(hosts) >= 1

    def test_search_hosts_by_mac(self, mock_mikrotik_api):
        hosts = hotspot_manager.search_hosts(self.ROUTER_KEY, "AA:BB:CC:DD:EE:01")
        found = [h for h in hosts if h.get("mac-address", "").lower() == "aa:bb:cc:dd:ee:01"]
        assert len(found) >= 1

    def test_search_hosts_skips_leases_when_no_match(self):
        from core.hotspot_manager import mikrotik_api

        mikrotik_api.execute = MagicMock(return_value=[])

        hosts = hotspot_manager.search_hosts(self.ROUTER_KEY, "no-match")

        assert hosts == []
        assert mikrotik_api.execute.call_count == 3
        assert mikrotik_api.execute.call_args_list[0].args[1] == "ip/hotspot/host/print"
        assert mikrotik_api.execute.call_args_list[1].args[1] == "ip/hotspot/host/print"
        assert mikrotik_api.execute.call_args_list[2].args[1] == "ip/hotspot/host/print"

    def test_kick_host_skips_leases_when_no_match(self):
        from core.hotspot_manager import mikrotik_api

        mikrotik_api.execute = MagicMock(return_value=[])

        success, host_name = hotspot_manager.kick_host(self.ROUTER_KEY, "192.0.2.1")

        assert success is False
        assert host_name is None
        assert mikrotik_api.execute.call_count == 3
        assert mikrotik_api.execute.call_args_list[0].args[1] == "ip/hotspot/host/print"
        assert mikrotik_api.execute.call_args_list[1].args[1] == "ip/hotspot/host/print"
        assert mikrotik_api.execute.call_args_list[2].args[1] == "ip/hotspot/host/print"

    def test_create_cards(self, mock_mikrotik_api):
        cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=3, length=4,
            card_system=CardSystem.DIFFERENT_CREDENTIALS,
            profile="default",
        )
        assert len(cards) == 3
        assert all(isinstance(c, CardData) for c in cards)
        # Ensure unique usernames
        usernames = [c.username for c in cards]
        assert len(set(usernames)) == 3

    def test_create_cards_unique_usernames(self, mock_mikrotik_api):
        cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=5, length=6,
            card_system=CardSystem.DIFFERENT_CREDENTIALS,
            profile="default",
        )
        usernames = [c.username for c in cards]
        assert len(set(usernames)) == 5

    def test_create_cards_same_credentials(self, mock_mikrotik_api):
        cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=2, length=4,
            card_system=CardSystem.SAME_CREDENTIALS,
            profile="default",
        )
        for c in cards:
            assert c.username == c.password

    def test_create_cards_empty_credentials(self, mock_mikrotik_api):
        cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=2, length=4,
            card_system=CardSystem.EMPTY_PASSWORD,
            profile="default",
        )
        for c in cards:
            assert c.password == ""

    def test_get_hotspot_stats(self, mock_mikrotik_api):
        stats = hotspot_manager.get_hotspot_stats(self.ROUTER_KEY)
        assert stats is not None
        assert stats["total"] >= 1
        assert stats["active"] >= 1
        assert "categories" in stats

    def test_parse_reset_day(self):
        from core.hotspot_manager import hotspot_manager as hm

        assert hm._parse_reset_day("BATCH_2026-07-05_10:00") == 5
        assert hm._parse_reset_day("PREFIX_2026-12-31_23:59") == 31
        assert hm._parse_reset_day("foo/12") == 12
        assert hm._parse_reset_day("no date here") is None

    def test_get_hotspot_stats_groups_resets_by_day(self):
        from core.hotspot_manager import mikrotik_api

        users = [
            {"name": "u1", "comment": "BATCH_2026-07-05_10:00", "limit-bytes-total": "1000000000", "disabled": "false"},
            {"name": "u2", "comment": "BATCH_2026-07-05_11:00", "limit-bytes-total": "2000000000", "disabled": "false"},
            {"name": "u3", "comment": "BATCH_2026-07-04_09:00", "limit-bytes-total": "1000000000", "disabled": "false"},
        ]
        mikrotik_api.execute = MagicMock(return_value=users)

        stats = hotspot_manager.get_hotspot_stats(self.ROUTER_KEY)
        assert stats["reset_days"] == [5, 4]
        assert len(stats["resets_by_day"][5]) == 2
        assert len(stats["resets_by_day"][4]) == 1
        assert stats["reset_list"] == []

        day5 = hotspot_manager.get_hotspot_stats(self.ROUTER_KEY, day=5)
        assert day5["selected_day"] == 5
        assert len(day5["reset_list"]) == 2

    def test_format_user(self, mock_mikrotik_api):
        user = hotspot_manager.get_user(self.ROUTER_KEY, "*1")
        assert user is not None
        formatted = hotspot_manager.format_user(user)
        assert "testuser1" in formatted
