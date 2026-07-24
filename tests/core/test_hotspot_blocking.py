"""Tests for core.hotspot_blocking — firewall address-list operations."""

from unittest.mock import MagicMock

from core.hotspot_blocking import block_mac, get_blocked_macs, unblock_mac


class TestBlockMac:
    def setup_method(self):
        self.api = MagicMock()
        self.router_key = "discovered_1"

    def test_successful_block(self):
        result = block_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is True
        self.api.execute.assert_called_once()
        call_args = self.api.execute.call_args
        assert call_args[0][1] == "ip/firewall/address-list/add"

    def test_invalid_mac_returns_false(self):
        result = block_mac(self.api, self.router_key, "not-a-mac")
        assert result is False
        self.api.execute.assert_not_called()

    def test_normalizes_mac(self):
        block_mac(self.api, self.router_key, "aa:bb:cc:dd:ee:ff")
        call_args = self.api.execute.call_args
        assert call_args[1]["address"] == "AA:BB:CC:DD:EE:FF"

    def test_sanitizes_comment(self):
        block_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF", "line1\nline2\rline3")
        call_args = self.api.execute.call_args
        assert "line1" in call_args[1]["comment"]
        assert "\n" not in call_args[1]["comment"]

    def test_truncates_long_comment(self):
        block_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF", "x" * 200)
        call_args = self.api.execute.call_args
        assert len(call_args[1]["comment"]) <= 100

    def test_api_error_returns_false(self):
        from librouteros.exceptions import LibRouterosError

        self.api.execute.side_effect = LibRouterosError("fail")
        result = block_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is False

    def test_connection_error_returns_false(self):
        self.api.execute.side_effect = ConnectionError("timeout")
        result = block_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is False


class TestUnblockMac:
    def setup_method(self):
        self.api = MagicMock()
        self.router_key = "discovered_1"

    def test_successful_unblock(self):
        self.api.execute.side_effect = [
            [{".id": "*1"}],
            [],
        ]
        result = unblock_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is True
        assert self.api.execute.call_count == 2

    def test_mac_not_found(self):
        self.api.execute.return_value = []
        result = unblock_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is False

    def test_no_entry_id(self):
        self.api.execute.return_value = [{"address": "AA:BB:CC:DD:EE:FF"}]
        result = unblock_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is False

    def test_api_error_returns_false(self):
        from librouteros.exceptions import LibRouterosError

        self.api.execute.side_effect = LibRouterosError("fail")
        result = unblock_mac(self.api, self.router_key, "AA:BB:CC:DD:EE:FF")
        assert result is False


class TestGetBlockedMacs:
    def setup_method(self):
        self.api = MagicMock()
        self.router_key = "discovered_1"

    def test_returns_list(self):
        self.api.execute.return_value = [
            {"address": "AA:BB:CC:DD:EE:FF", "comment": "blocked", "creation-time": "123"},
        ]
        result = get_blocked_macs(self.api, self.router_key)
        assert len(result) == 1
        assert result[0]["address"] == "AA:BB:CC:DD:EE:FF"

    def test_filters_non_dict(self):
        self.api.execute.return_value = ["bad", {"address": "AA:BB:CC:DD:EE:FF"}]
        result = get_blocked_macs(self.api, self.router_key)
        assert len(result) == 1

    def test_empty_list(self):
        self.api.execute.return_value = []
        result = get_blocked_macs(self.api, self.router_key)
        assert result == []

    def test_api_error_returns_empty(self):
        from librouteros.exceptions import LibRouterosError

        self.api.execute.side_effect = LibRouterosError("fail")
        result = get_blocked_macs(self.api, self.router_key)
        assert result == []
