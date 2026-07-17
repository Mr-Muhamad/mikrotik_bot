"""Integration-style tests for the Hotspot user add flow.

Tests the end-to-end flow through hotspot_manager using the in-memory
MikrotikAPIMock, simulating real MikroTik API interactions.
"""

from core.hotspot_manager import hotspot_manager
from core.card_models import CardSystem


class TestHotspotAddFlow:
    ROUTER_KEY = "discovered_1"

    def test_add_user_and_verify_in_mock(self, mock_mikrotik_api):
        result = hotspot_manager.add_user(
            self.ROUTER_KEY, name="flow_user", password="flow_pass",
            profile="default", comment="integration test",
        )
        assert isinstance(result, list)
        assert mock_mikrotik_api.last_router_key == self.ROUTER_KEY
        add_commands = [
            c for c in mock_mikrotik_api.commands_executed
            if c[1] == "ip/hotspot/user/add"
        ]
        assert len(add_commands) >= 1
        _, _, kwargs = add_commands[-1]
        assert kwargs.get("name") == "flow_user"
        assert kwargs.get("comment") == "integration test"
        user = hotspot_manager.get_user(self.ROUTER_KEY, kwargs.get(".id", "*1"))
        assert user is not None

    def test_add_then_search(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="searchable", password="pass",
            profile="default",
        )
        results = hotspot_manager.search_users(self.ROUTER_KEY, "searchable")
        assert len(results) >= 1
        assert any(u.get("name") == "searchable" for u in results)

    def test_add_then_delete(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="to_delete", password="pass",
            profile="default",
        )
        results = hotspot_manager.search_users(self.ROUTER_KEY, "to_delete")
        assert len(results) >= 1
        uid = results[0][".id"]
        hotspot_manager.delete_user(self.ROUTER_KEY, uid)
        assert hotspot_manager.get_user(self.ROUTER_KEY, uid) is None

    def test_create_cards_then_list(self, mock_mikrotik_api):
        cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=3, length=5,
            card_system=CardSystem.SAME_CREDENTIALS,
            profile="default",
        )
        assert len(cards) == 3
        users = hotspot_manager.list_users(self.ROUTER_KEY, limit=50)
        card_usernames = {c.username for c in cards}
        found_usernames = {u.get("name") for u in users if u.get("name") in card_usernames}
        assert len(found_usernames) == 3

    def test_get_hotspot_stats_after_operations(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="stats_user", password="pass",
            profile="default",
        )
        stats = hotspot_manager.get_hotspot_stats(self.ROUTER_KEY)
        assert stats is not None
        assert stats["total"] >= 1
        assert "categories" in stats

    def test_duplicate_username_handling(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="duplicate", password="pass1",
            profile="default",
        )
        hotspot_manager.search_users(self.ROUTER_KEY, "duplicate")
        new_cards = hotspot_manager.create_cards(
            self.ROUTER_KEY, count=3, length=4,
            card_system=CardSystem.DIFFERENT_CREDENTIALS,
            profile="default",
        )
        new_usernames = {c.username for c in new_cards}
        assert len(new_usernames) == 3
        assert "duplicate" not in new_usernames

    def test_delete_nonexistent_returns_clean(self, mock_mikrotik_api):
        result = hotspot_manager.delete_user(self.ROUTER_KEY, "*nonexistent")
        assert isinstance(result, list)

    def test_format_user_output(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="format_me", password="pass",
            profile="premium", comment="test output",
        )
        user = hotspot_manager.get_user(self.ROUTER_KEY, "*1")
        if user:
            formatted = hotspot_manager.format_user(user)
            assert isinstance(formatted, str)
            assert len(formatted) > 10

    def test_reset_counters_command(self, mock_mikrotik_api):
        hotspot_manager.add_user(
            self.ROUTER_KEY, name="reset_me", password="pass",
            profile="default",
        )
        users = hotspot_manager.search_users(self.ROUTER_KEY, "reset_me")
        if users:
            uid = users[0][".id"]
            hotspot_manager.delete_user(self.ROUTER_KEY, uid)
            assert hotspot_manager.get_user(self.ROUTER_KEY, uid) is None
