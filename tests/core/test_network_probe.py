"""Tests for core.network_probe — pure helpers and probe classes."""

import socket
import struct
from unittest.mock import MagicMock

import pytest

from core.network_probe import (
    ARPTableProbe,
    DiscoveredRouter,
    MNDPListenerProbe,
    PortScanProbe,
    decode_mndp_packet,
    merge_probe_results,
    parse_arp_table_linux,
    parse_arp_table_windows,
)
from core.network_probe import (
    MNDP_TYPE_IDENTITY,
    MNDP_TYPE_IPV4,
    MNDP_TYPE_MAC,
    MNDP_TYPE_VERSION,
)

# ─── Pure helper tests ────────────────────────────────────────


class TestDecodeMndpPacket:
    def test_returns_empty_for_short_data(self):
        assert decode_mndp_packet(b"") == {}
        assert decode_mndp_packet(b"\x00") == {}

    def test_decodes_mac(self):
        # Type=1 (MAC), Length=6, Payload=MAC bytes
        mac_bytes = b"\xaa\xbb\xcc\xdd\xee\xff"
        packet = b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_MAC, 6) + mac_bytes
        result = decode_mndp_packet(packet)
        assert result["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_decodes_identity(self):
        identity = b"RouterOS-Test"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity))
            + identity
        )
        result = decode_mndp_packet(packet)
        assert result["identity"] == "RouterOS-Test"

    def test_decodes_version(self):
        version = b"6.48.6"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_VERSION, len(version))
            + version
        )
        result = decode_mndp_packet(packet)
        assert result["version"] == "6.48.6"

    def test_decodes_uptime(self):
        # Uptime type=10, 4 bytes (little-endian seconds)
        uptime_payload = struct.pack("<I", 90061)  # 1d 1h 1m 1s
        packet = b"\x00\x00\x00\x00" + struct.pack(">HH", 10, 4) + uptime_payload
        result = decode_mndp_packet(packet)
        assert "1d" in result["uptime"]
        assert "1h" in result["uptime"]

    def test_decodes_ipv4(self):
        ipv4_bytes = socket.inet_aton("192.168.1.1")
        packet = (
            b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_IPV4, 4) + ipv4_bytes
        )
        result = decode_mndp_packet(packet)
        assert result["ipv4"] == "192.168.1.1"

    def test_handles_truncated_length(self):
        # Length claims more data than available — should break gracefully
        packet = (
            b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_IDENTITY, 100) + b"short"
        )
        result = decode_mndp_packet(packet)
        assert result == {}

    def test_handles_invalid_utf8_in_identity(self):
        identity = b"\xff\xfe invalid"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity))
            + identity
        )
        result = decode_mndp_packet(packet)
        assert "identity" in result


class TestParseArpTableWindows:
    def test_parses_dynamic_entries(self):
        output = """
Interface: 192.168.1.100
  Internet Address      Physical Address      Type
  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic
  192.168.1.2           11-22-33-44-55-66     dynamic
  192.168.1.3           00-00-00-00-00-00     static
"""
        result = parse_arp_table_windows(output)
        assert "192.168.1.1" in result
        assert "192.168.1.2" in result
        assert "192.168.1.3" not in result  # zero MAC excluded
        assert result["192.168.1.1"] == "aa:bb:cc:dd:ee:ff"

    def test_returns_empty_for_no_entries(self):
        result = parse_arp_table_windows("")
        assert result == {}

    def test_skips_static_zero_mac(self):
        output = "  10.0.0.1             00-00-00-00-00-00     static"
        result = parse_arp_table_windows(output)
        assert "10.0.0.1" not in result


class TestParseArpTableLinux:
    def test_parses_neigh_output(self):
        output = """192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
192.168.1.2 dev eth0 lladdr 11:22:33:44:55:66 STALE
10.0.0.1 dev eth0  FAILED
"""
        result = parse_arp_table_linux(output)
        assert "192.168.1.1" in result
        assert "192.168.1.2" in result
        assert "10.0.0.1" not in result  # no MAC

    def test_skips_short_lines(self):
        output = "incomplete line"
        result = parse_arp_table_linux(output)
        assert result == {}


# ─── Probe tests ───────────────────────────────────────────────


class TestARPTableProbe:
    def test_discover_windows(self):
        run_fn = MagicMock(
            return_value=MagicMock(
                stdout="  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic\n"
            )
        )
        probe = ARPTableProbe(run_fn=run_fn, system="Windows")
        result = probe.discover()
        assert len(result) == 1
        assert result[0]["ip"] == "192.168.1.1"
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result[0]["source"] == "arp"

    def test_discover_linux(self):
        run_fn = MagicMock(
            return_value=MagicMock(
                stdout="192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE\n"
            )
        )
        probe = ARPTableProbe(run_fn=run_fn, system="Linux")
        result = probe.discover()
        assert len(result) == 1
        assert result[0]["ip"] == "192.168.1.1"

    def test_discover_unsupported_system(self):
        probe = ARPTableProbe(run_fn=MagicMock(), system="FreeBSD")
        result = probe.discover()
        assert result == []

    def test_discover_handles_subprocess_error(self):
        def failing_run(*a, **kw):
            raise OSError("no such command")

        probe = ARPTableProbe(run_fn=failing_run, system="Windows")
        result = probe.discover()
        assert result == []


class TestPortScanProbe:
    @pytest.mark.asyncio
    async def test_returns_open_ips(self):
        async def fake_open(ip, port):
            return (MagicMock(), MagicMock())

        probe = PortScanProbe(
            ips=["1.2.3.4", "5.6.7.8"],
            port=8728,
            timeout=1.0,
            open_connection=fake_open,
        )
        result = await probe.discover()
        assert len(result) == 2
        for entry in result:
            assert entry["source"] == "port_check"
            assert entry["port"] == 8728

    @pytest.mark.asyncio
    async def test_filters_closed_ips(self):
        async def selective_open(ip, port):
            if ip == "1.2.3.4":
                return (MagicMock(), MagicMock())
            raise ConnectionRefusedError("nope")

        probe = PortScanProbe(
            ips=["1.2.3.4", "5.6.7.8"], open_connection=selective_open
        )
        result = await probe.discover()
        assert len(result) == 1
        assert result[0]["ip"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_empty_ips(self):
        probe = PortScanProbe(ips=[])
        result = await probe.discover()
        assert result == []

    @pytest.mark.asyncio
    async def test_all_closed(self):
        async def always_fail(ip, port):
            raise ConnectionRefusedError()

        probe = PortScanProbe(ips=["1.2.3.4"], open_connection=always_fail)
        result = await probe.discover()
        assert result == []


class TestMNDPListenerProbe:
    @pytest.mark.asyncio
    async def test_discover_handles_socket_error(self):
        """OSError from socket creation is caught inside _discover_sync, returns []."""
        probe = MNDPListenerProbe(
            timeout=0.1, socket_factory=MagicMock(side_effect=OSError("no socket"))
        )
        result = await probe.discover()
        assert result == []

    @pytest.mark.asyncio
    async def test_discover_propagates_permission_error(self):
        """PermissionError from socket creation propagates to caller."""
        sock_factory = MagicMock(side_effect=PermissionError("need admin"))
        probe = MNDPListenerProbe(timeout=0.1, socket_factory=sock_factory)
        with pytest.raises(PermissionError):
            await probe.discover()


# ─── Orchestrator merge tests ─────────────────────────────────


class TestMergeProbeResults:
    def test_port_only(self):
        port = [{"ip": "1.2.3.4", "port": 8728, "source": "port_check"}]
        result = merge_probe_results([], port, [])
        assert len(result) == 1
        assert result[0].ip_address == "1.2.3.4"
        assert result[0].source == "port_check"

    def test_arp_only(self):
        arp = [{"ip": "1.2.3.4", "mac": "aa:bb:cc:dd:ee:ff", "source": "arp"}]
        result = merge_probe_results(arp, [], [])
        assert len(result) == 1
        assert result[0].mac_address == "aa:bb:cc:dd:ee:ff"

    def test_mndp_only(self):
        mndp = [
            {
                "ip": "1.2.3.4",
                "identity": "Router1",
                "version": "6.48",
                "source": "mndp",
            }
        ]
        result = merge_probe_results([], [], mndp)
        assert len(result) == 1
        assert result[0].identity == "Router1"
        assert result[0].version == "6.48"

    def test_arp_plus_port_enriches_mac(self):
        arp = [{"ip": "1.2.3.4", "mac": "aa:bb:cc:dd:ee:ff", "source": "arp"}]
        port = [{"ip": "1.2.3.4", "port": 8728, "source": "port_check"}]
        result = merge_probe_results(arp, port, [])
        assert len(result) == 1
        assert result[0].mac_address == "aa:bb:cc:dd:ee:ff"
        assert "port" in result[0].source

    def test_mndp_enriches_existing(self):
        port = [{"ip": "1.2.3.4", "port": 8728, "source": "port_check"}]
        mndp = [
            {
                "ip": "1.2.3.4",
                "identity": "MyRouter",
                "version": "6.48.6",
                "source": "mndp",
            }
        ]
        result = merge_probe_results([], port, mndp)
        assert len(result) == 1
        assert result[0].identity == "MyRouter"
        assert result[0].version == "6.48.6"

    def test_dedup_by_ip(self):
        arp = [
            {"ip": "1.2.3.4", "mac": "aa:bb:cc:dd:ee:ff", "source": "arp"},
            {"ip": "1.2.3.5", "mac": "11:22:33:44:55:66", "source": "arp"},
        ]
        port = [{"ip": "1.2.3.4", "port": 8728, "source": "port_check"}]
        result = merge_probe_results(arp, port, [])
        assert len(result) == 2
        assert {r.ip_address for r in result} == {"1.2.3.4", "1.2.3.5"}

    def test_empty_inputs(self):
        assert merge_probe_results([], [], []) == []


# ─── DiscoveredRouter tests ────────────────────────────────────


class TestDiscoveredRouter:
    def test_display_name_uses_ip_when_unknown(self):
        r = DiscoveredRouter(ip_address="1.2.3.4")
        assert r.display_name() == "1.2.3.4"

    def test_display_name_with_version_and_board(self):
        r = DiscoveredRouter(
            ip_address="1.2.3.4", identity="MyR", version="6.48", board="RB951"
        )
        assert "MyR" in r.display_name()
        assert "v6.48" in r.display_name()
        assert "RB951" in r.display_name()

    def test_display_line_includes_ip_and_port(self):
        r = DiscoveredRouter(ip_address="1.2.3.4", port=8728, identity="MyR")
        line = r.display_line()
        assert "1.2.3.4" in line
        assert "8728" in line
        assert "MyR" in line

    def test_display_line_uses_green_when_version_present(self):
        r = DiscoveredRouter(ip_address="1.2.3.4", version="6.48")
        assert "🟢" in r.display_line()

    def test_display_line_uses_yellow_when_no_version(self):
        r = DiscoveredRouter(ip_address="1.2.3.4")
        assert "🟡" in r.display_line()
