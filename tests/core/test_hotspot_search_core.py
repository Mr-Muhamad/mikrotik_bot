"""Tests for core.hotspot_search — host search, DHCP enrichment, and kick."""

from unittest.mock import MagicMock

from core.hotspot_search import (
    get_leases_by_mac,
    kick_host,
    kick_user,
    search_hosts,
)


def _host(mid: str, mac: str, ip: str, user: str = "") -> dict:  # type: ignore[reportMissingTypeArgument]
    return {".id": mid, "mac-address": mac, "address": ip, "user": user}


def _lease(mac: str, host_name: str = "") -> dict:  # type: ignore[reportMissingTypeArgument]
    return {"mac-address": mac, "host-name": host_name}


class TestGetLeasesByMac:
    def setup_method(self):
        self.api = MagicMock()
        self.rk = "discovered_1"

    def test_filters_by_matching_macs(self):
        self.api.execute.return_value = [
            _lease("aa:bb:cc:dd:ee:ff", "dev1"),
            _lease("11:22:33:44:55:66", "dev2"),
        ]
        result = get_leases_by_mac(self.api, self.rk, {"aa:bb:cc:dd:ee:ff"})
        assert len(result) == 1
        assert result["aa:bb:cc:dd:ee:ff"]["host-name"] == "dev1"

    def test_returns_empty_for_no_match(self):
        self.api.execute.return_value = [_lease("aa:bb:cc:dd:ee:ff")]
        result = get_leases_by_mac(self.api, self.rk, {"ff:ff:ff:ff:ff:ff"})
        assert result == {}

    def test_lowercases_mac_keys(self):
        self.api.execute.return_value = [_lease("AA:BB:CC:DD:EE:FF")]
        result = get_leases_by_mac(self.api, self.rk, {"aa:bb:cc:dd:ee:ff"})
        assert "aa:bb:cc:dd:ee:ff" in result

    def test_empty_macs_set_returns_empty(self):
        self.api.execute.return_value = [_lease("aa:bb:cc:dd:ee:ff")]
        result = get_leases_by_mac(self.api, self.rk, set())
        assert result == {}


class TestSearchHosts:
    def setup_method(self):
        self.api = MagicMock()
        self.rk = "discovered_1"

    def test_finds_host_by_mac(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        self.api.execute.side_effect = [hosts, []]
        result = search_hosts(self.api, self.rk, "aa:bb:cc:dd:ee:ff")
        assert len(result) == 1

    def test_falls_back_to_ip_search(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        self.api.execute.side_effect = [[], hosts, []]
        result = search_hosts(self.api, self.rk, "10.0.0.1")
        assert len(result) == 1

    def test_falls_back_to_partial_match(self):
        all_hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        self.api.execute.side_effect = [[], [], all_hosts, []]
        result = search_hosts(self.api, self.rk, "10.0.0")
        assert len(result) == 1

    def test_returns_empty_when_no_match(self):
        self.api.execute.side_effect = [[], [], []]
        result = search_hosts(self.api, self.rk, "nonexistent")
        assert result == []

    def test_enriches_host_name_from_dhcp(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        leases = [_lease("aa:bb:cc:dd:ee:ff", "MyDevice")]
        self.api.execute.side_effect = [hosts, leases]
        result = search_hosts(self.api, self.rk, "aa:bb:cc:dd:ee:ff")
        assert result[0]["host-name"] == "MyDevice"

    def test_handles_api_exception_gracefully(self):
        self.api.execute.side_effect = [Exception("timeout"), [], []]
        result = search_hosts(self.api, self.rk, "aa:bb:cc:dd:ee:ff")
        assert result == []


class TestKickHost:
    def setup_method(self):
        self.api = MagicMock()
        self.rk = "discovered_1"

    def test_kicks_host_by_mac(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1", "user1")]
        self.api.execute.side_effect = [hosts, [], []]
        ok, name = kick_host(self.api, self.rk, "aa:bb:cc:dd:ee:ff")
        assert ok is True
        assert name is not None

    def test_returns_false_when_not_found(self):
        self.api.execute.side_effect = [[], [], []]
        ok, name = kick_host(self.api, self.rk, "ff:ff:ff:ff:ff:ff")
        assert ok is False
        assert name is None

    def test_kicks_host_by_ip_fallback(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        self.api.execute.side_effect = [[], hosts, [], []]
        ok, name = kick_host(self.api, self.rk, "10.0.0.1")  # type: ignore[reportUnusedVariable]
        assert ok is True

    def test_sends_remove_command(self):
        hosts = [_host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")]
        self.api.execute.side_effect = [hosts, [], []]
        kick_host(self.api, self.rk, "aa:bb:cc:dd:ee:ff")
        last_call = self.api.execute.call_args_list[-1]
        assert "host/remove" in last_call[0][1]

    def test_enriches_name_from_lease(self):
        host = _host("1", "aa:bb:cc:dd:ee:ff", "10.0.0.1")
        lease = [_lease("aa:bb:cc:dd:ee:ff", "RouterDevice")]
        self.api.execute.side_effect = [[host], lease, []]
        ok, name = kick_host(self.api, self.rk, "aa:bb:cc:dd:ee:ff")  # type: ignore[reportUnusedVariable]
        assert name == "RouterDevice"


class TestKickUser:
    def setup_method(self):
        self.api = MagicMock()
        self.rk = "discovered_1"

    def test_returns_empty_when_no_hosts(self):
        self.api.execute.side_effect = [
            [],
            [],
            [],
        ]
        result = kick_user(self.api, self.rk, "testuser")
        assert result == []

    def test_kicks_matching_host(self):
        active = [{".id": "a1", "user": "testuser", "mac-address": ""}]
        hosts = [_host("h1", "aa:bb:cc:dd:ee:ff", "10.0.0.1", "testuser")]
        self.api.execute.side_effect = [
            active,
            [],
            hosts,
            [],
            [],
        ]
        result = kick_user(self.api, self.rk, "testuser")
        assert len(result) >= 1

    def test_deduplicates_kicked_names(self):
        active = [
            {".id": "a1", "user": "u1", "mac-address": "aa:bb:cc:dd:ee:ff"},
        ]
        hosts = [
            _host("h1", "aa:bb:cc:dd:ee:ff", "10.0.0.1", "u1"),
            _host("h2", "aa:bb:cc:dd:ee:ff", "10.0.0.2", "u1"),
        ]
        self.api.execute.side_effect = [
            active,
            hosts,
            [],
            [],
        ]
        result = kick_user(self.api, self.rk, "u1")
        assert len(result) == len(set(result))

    def test_removes_active_sessions(self):
        active = [{".id": "a1", "user": "u1", "mac-address": "aa:bb:cc:dd:ee:ff"}]
        self.api.execute.side_effect = [active, [], [], []]
        kick_user(self.api, self.rk, "u1")
        remove_calls = [
            c for c in self.api.execute.call_args_list
            if "active/remove" in c[0][1]
        ]
        assert len(remove_calls) == 1
