"""Extended tests for core.network_probe — coverage gaps."""

import socket
import struct
import time
from unittest.mock import MagicMock, patch

from core.network_probe import (
    MNDP_DISCOVERY_PAYLOAD,
    MNDP_PORT,
    MNDP_TYPE_IDENTITY,
    MNDP_TYPE_IPV4,
    MNDP_TYPE_MAC,
    MNDP_TYPE_UPTIME,
    MNDP_TYPE_VERSION,
    DiscoveredRouter,
    MNDPListenerProbe,
    _get_local_ips,  # type: ignore[reportPrivateUsage]
    _merge_mndp_results,  # type: ignore[reportPrivateUsage]
    _merge_port_results,  # type: ignore[reportPrivateUsage]
    decode_mndp_packet,
    merge_probe_results,
)


class TestDecodeMndpExtended:
    def test_decode_error_on_string_type(self):
        raw = b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_IDENTITY, 4) + b"test"
        with patch("core.network_probe.bytes", side_effect=AttributeError("no bytes")):
            result = decode_mndp_packet(raw)
        assert "identity" not in result

    def test_ipv4_decode_error(self):
        bad_payload = b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_IPV4, 2) + b"\x00\x00"
        with patch("socket.inet_ntop", side_effect=OSError("bad ip")):
            result = decode_mndp_packet(bad_payload)
        assert "ipv4" not in result

    def test_uptime_short_payload(self):
        packet = b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_UPTIME, 2) + b"\x00\x00"
        result = decode_mndp_packet(packet)
        assert "uptime" not in result

    def test_truncated_type_field(self):
        packet = b"\x00\x00\x00\x00" + b"\x00"
        result = decode_mndp_packet(packet)
        assert result == {}

    def test_all_attributes_combined(self):
        mac = b"\xaa\xbb\xcc\xdd\xee\xff"
        identity = b"Router1"
        version = b"7.12"
        uptime_sec = struct.pack("<I", 3661)
        ipv4 = socket.inet_aton("10.0.0.1")
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_MAC, 6) + mac
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
            + struct.pack(">HH", MNDP_TYPE_VERSION, len(version)) + version
            + struct.pack(">HH", MNDP_TYPE_UPTIME, 4) + uptime_sec
            + struct.pack(">HH", MNDP_TYPE_IPV4, 4) + ipv4
        )
        result = decode_mndp_packet(packet)
        assert result["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result["identity"] == "Router1"
        assert result["version"] == "7.12"
        assert "1h" in result["uptime"]
        assert result["ipv4"] == "10.0.0.1"


class TestDiscoveredRouterExtended:
    def test_display_line_with_board_and_uptime(self):
        r = DiscoveredRouter(
            ip_address="10.0.0.1",
            identity="TestRouter",
            version="7.12",
            board="RB4011",
            uptime="2d 3h 4m",
            port=8728,
        )
        line = r.display_line()
        assert "TestRouter" in line
        assert "v7.12" in line
        assert "RB4011" in line
        assert "2d 3h 4m" in line
        assert "🟢" in line

    def test_display_line_unknown_identity(self):
        r = DiscoveredRouter(ip_address="10.0.0.1")
        line = r.display_line()
        assert "راوتر MikroTik" in line
        assert "10.0.0.1" in line
        assert "🌐" in line

    def test_display_line_no_version_no_board_no_uptime(self):
        r = DiscoveredRouter(ip_address="1.2.3.4", identity="R1")
        line = r.display_line()
        assert "R1" in line
        assert "1.2.3.4:8728" in line

    def test_display_name_version_only(self):
        r = DiscoveredRouter(ip_address="1.2.3.4", identity="R1", version="6.49")
        name = r.display_name()
        assert "R1" in name
        assert "v6.49" in name
        assert "RB" not in name


class TestGetLocalIps:
    def test_always_includes_loopback(self):
        result = _get_local_ips()
        assert "127.0.0.1" in result

    def test_handles_getaddrinfo_error(self):
        with patch("socket.getaddrinfo", side_effect=OSError("fail")):
            result = _get_local_ips()
        assert "127.0.0.1" in result

    def test_handles_gaierror(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("fail")):
            result = _get_local_ips()
        assert "127.0.0.1" in result

    def test_adds_found_ips(self):
        fake_info = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.100", 0))]
        with patch("socket.getaddrinfo", return_value=fake_info):
            result = _get_local_ips()
        assert "192.168.1.100" in result
        assert "127.0.0.1" in result


class TestMNDPSetupSocket:
    def _make_probe(self, factory):  # type: ignore[reportMissingParameterType]
        return MNDPListenerProbe(timeout=1.0, socket_factory=factory)

    def test_basic_setup(self):
        sock = MagicMock()
        factory = MagicMock(return_value=sock)
        probe = self._make_probe(factory)
        result = probe._setup_socket()  # type: ignore[reportPrivateUsage]
        factory.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind.assert_called_once_with(("", MNDP_PORT))
        sock.settimeout.assert_called_once_with(1.0)
        assert result is sock

    def test_reuseport_success(self):
        sock = MagicMock()
        factory = MagicMock(return_value=sock)
        probe = self._make_probe(factory)
        probe._setup_socket()  # type: ignore[reportPrivateUsage]
        so_reuse_port = getattr(socket, "SO_REUSEPORT", None)
        if so_reuse_port is not None:
            sock.setsockopt.assert_any_call(socket.SOL_SOCKET, so_reuse_port, 1)

    def test_reuseport_fallback(self):
        sock = MagicMock()
        sock.setsockopt.side_effect = lambda *a: None
        original = getattr(socket, "SO_REUSEPORT", None)
        if original is not None:
            with patch.object(socket, "SO_REUSEPORT", original):
                call_count = [0]
                def selective_setsockopt(*args):  # type: ignore[reportMissingParameterType]
                    call_count[0] += 1
                    if call_count[0] == 2 and args[1] == original:
                        raise OSError("not supported")
                    return None
                sock.setsockopt.side_effect = selective_setsockopt
                factory = MagicMock(return_value=sock)
                probe = self._make_probe(factory)
                probe._setup_socket()  # type: ignore[reportPrivateUsage]
                sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def test_no_reuseport_attr(self):
        sock = MagicMock()
        factory = MagicMock(return_value=sock)
        probe = self._make_probe(factory)
        with patch.object(socket, "SO_REUSEPORT", None, create=True):
            probe._setup_socket()  # type: ignore[reportPrivateUsage]
        sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


class TestMNDSendBroadcast:
    def test_sends_when_interval_elapsed(self):
        sock = MagicMock()
        probe = MNDPListenerProbe(timeout=1.0)
        result = probe._send_broadcast(sock, 0.0)  # type: ignore[reportPrivateUsage]
        sock.sendto.assert_called_once_with(MNDP_DISCOVERY_PAYLOAD, ("255.255.255.255", MNDP_PORT))
        assert result > 0

    def test_skips_when_interval_not_elapsed(self):
        sock = MagicMock()
        probe = MNDPListenerProbe(timeout=1.0)
        now = time.time()
        result = probe._send_broadcast(sock, now)  # type: ignore[reportPrivateUsage]
        sock.sendto.assert_not_called()
        assert result == now

    def test_handles_send_error(self):
        sock = MagicMock()
        sock.sendto.side_effect = OSError("send failed")
        probe = MNDPListenerProbe(timeout=1.0)
        result = probe._send_broadcast(sock, 0.0)  # type: ignore[reportPrivateUsage]
        sock.sendto.assert_called_once()
        assert result == 0.0


class TestMNDPProcessPacket:
    def test_skips_local_ip(self):
        discovered = {}
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(b"\x00\x00\x00\x00", "127.0.0.1", {"127.0.0.1"}, discovered)  # type: ignore[reportPrivateUsage]
        assert discovered == {}

    def test_skips_no_identity_no_board(self):
        mac = b"\xaa\xbb\xcc\xdd\xee\xff"
        packet = b"\x00\x00\x00\x00" + struct.pack(">HH", MNDP_TYPE_MAC, 6) + mac
        discovered = {}
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(packet, "10.0.0.1", set(), discovered)  # type: ignore[reportPrivateUsage]
        assert discovered == {}

    def test_creates_new_entry_with_identity(self):
        identity = b"Router1"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
        )
        discovered = {}
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(packet, "10.0.0.1", set(), discovered)  # type: ignore[reportPrivateUsage]
        assert "10.0.0.1" in discovered
        assert discovered["10.0.0.1"]["identity"] == "Router1"
        assert discovered["10.0.0.1"]["source"] == "mndp"

    def test_updates_existing_entry(self):
        identity = b"Router1"
        version = b"7.12"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
            + struct.pack(">HH", MNDP_TYPE_VERSION, len(version)) + version
        )
        discovered = {
            "10.0.0.1": {
                "ip": "10.0.0.1",
                "source": "mndp",
                "identity": "OldName",
                "last_seen": "2020-01-01",
            }
        }
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(packet, "10.0.0.1", set(), discovered)  # type: ignore[reportPrivateUsage]
        assert discovered["10.0.0.1"]["identity"] == "Router1"
        assert discovered["10.0.0.1"]["version"] == "7.12"
        assert discovered["10.0.0.1"]["last_seen"] != "2020-01-01"

    def test_ipv4_overrides_ip(self):
        identity = b"R1"
        ipv4_bytes = socket.inet_aton("192.168.1.100")
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
            + struct.pack(">HH", MNDP_TYPE_IPV4, 4) + ipv4_bytes
        )
        discovered = {}
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(packet, "10.0.0.1", set(), discovered)  # type: ignore[reportPrivateUsage]
        assert discovered["10.0.0.1"]["ip"] == "192.168.1.100"

    def test_does_not_overwrite_existing_non_empty_attrs(self):
        identity = b"NewRouter"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
        )
        discovered = {
            "10.0.0.1": {
                "ip": "10.0.0.1",
                "source": "mndp",
                "identity": "ExistingRouter",
                "version": "7.12",
                "last_seen": "2020-01-01",
            }
        }
        probe = MNDPListenerProbe(timeout=1.0)
        probe._process_packet(packet, "10.0.0.1", set(), discovered)  # type: ignore[reportPrivateUsage]
        assert discovered["10.0.0.1"]["identity"] == "NewRouter"
        assert discovered["10.0.0.1"]["version"] == "7.12"


class TestMNDPDiscoverSync:
    def test_returns_discovered_routers(self):
        identity = b"Router1"
        packet = (
            b"\x00\x00\x00\x00"
            + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
        )
        fake_sock = MagicMock()
        fake_sock.recvfrom.return_value = (packet, ("10.0.0.1", 5678))
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.3, socket_factory=factory)
        result = probe._discover_sync()  # type: ignore[reportPrivateUsage]
        assert len(result) >= 1
        assert result[0]["ip"] == "10.0.0.1"

    def test_handles_recv_timeout(self):
        fake_sock = MagicMock()
        fake_sock.recvfrom.side_effect = TimeoutError("timeout")
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.1, socket_factory=factory)
        result = probe._discover_sync()  # type: ignore[reportPrivateUsage]
        assert result == []

    def test_handles_recv_oserror(self):
        fake_sock = MagicMock()
        fake_sock.recvfrom.side_effect = OSError("recv failed")
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.1, socket_factory=factory)
        result = probe._discover_sync()  # type: ignore[reportPrivateUsage]
        assert result == []

    def test_closes_socket_in_finally(self):
        fake_sock = MagicMock()
        fake_sock.recvfrom.side_effect = TimeoutError
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.05, socket_factory=factory)
        probe._discover_sync()  # type: ignore[reportPrivateUsage]
        fake_sock.close.assert_called()

    def test_handles_close_error_in_finally(self):
        fake_sock = MagicMock()
        fake_sock.recvfrom.side_effect = TimeoutError
        fake_sock.close.side_effect = OSError("already closed")
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.05, socket_factory=factory)
        result = probe._discover_sync()  # type: ignore[reportPrivateUsage]
        assert result == []

    def test_filters_out_local_ip(self):
        with patch("core.network_probe._get_local_ips", return_value={"10.0.0.1", "127.0.0.1"}):
            identity = b"Router1"
            packet = (
                b"\x00\x00\x00\x00"
                + struct.pack(">HH", MNDP_TYPE_IDENTITY, len(identity)) + identity
            )
            fake_sock = MagicMock()
            fake_sock.recvfrom.return_value = (packet, ("10.0.0.1", 5678))
            fake_sock.setsockopt.return_value = None
            factory = MagicMock(return_value=fake_sock)

            probe = MNDPListenerProbe(timeout=0.15, socket_factory=factory)
            result = probe._discover_sync()  # type: ignore[reportPrivateUsage]
            assert result == []

    def test_sends_broadcast_in_loop(self):
        fake_sock = MagicMock()
        fake_sock.recvfrom.side_effect = TimeoutError
        fake_sock.setsockopt.return_value = None
        factory = MagicMock(return_value=fake_sock)

        probe = MNDPListenerProbe(timeout=0.2, socket_factory=factory)
        probe._discover_sync()  # type: ignore[reportPrivateUsage]
        assert fake_sock.sendto.called


class TestMergeResultsExtended:
    def test_merge_mndp_empty_ipv4_skipped(self):
        by_ip = {}
        mndp = [{"ip": "", "identity": "R1", "source": "mndp", "last_seen": "2024-01-01"}]
        _merge_mndp_results(mndp, by_ip, "2024-01-01")  # type: ignore[reportArgumentType]
        assert by_ip == {}

    def test_merge_mndp_no_ip_key_skipped(self):
        by_ip = {}
        mndp = [{"identity": "R1", "source": "mndp", "last_seen": "2024-01-01"}]
        _merge_mndp_results(mndp, by_ip, "2024-01-01")  # type: ignore[reportArgumentType]
        assert by_ip == {}

    def test_merge_mndp_enriches_existing_with_ipv4(self):
        by_ip = {
            "10.0.0.1": DiscoveredRouter(
                ip_address="10.0.0.1", source="port_check", identity="Unknown"
            )
        }
        mndp = [
            {
                "ipv4": "10.0.0.1",
                "identity": "Router1",
                "version": "7.12",
                "mac": "aa:bb:cc:dd:ee:ff",
                "board": "RB4011",
                "uptime": "1d 2h",
                "source": "mndp",
                "last_seen": "2024-06-01",
            }
        ]
        _merge_mndp_results(mndp, by_ip, "2024-01-01")  # type: ignore[reportArgumentType]
        r = by_ip["10.0.0.1"]
        assert r.identity == "Router1"
        assert r.version == "7.12"
        assert "mndp" in r.source

    def test_merge_mndp_creates_new_entry_with_ipv4(self):
        by_ip = {}
        mndp = [
            {
                "ipv4": "10.0.0.2",
                "identity": "NewRouter",
                "version": "7.12",
                "board": "hEX",
                "source": "mndp",
                "last_seen": "2024-01-01",
            }
        ]
        _merge_mndp_results(mndp, by_ip, "2024-01-01")  # type: ignore[reportArgumentType]
        assert "10.0.0.2" in by_ip
        assert by_ip["10.0.0.2"].identity == "NewRouter"

    def test_merge_mndp_falls_back_to_ip_key(self):
        by_ip = {}
        mndp = [
            {
                "ip": "10.0.0.3",
                "identity": "Fallback",
                "source": "mndp",
                "last_seen": "2024-01-01",
            }
        ]
        _merge_mndp_results(mndp, by_ip, "2024-01-01")  # type: ignore[reportArgumentType]
        assert "10.0.0.3" in by_ip

    def test_merge_port_results_basic(self):
        port = [{"ip": "10.0.0.1", "mac": "aa:bb:cc:dd:ee:ff", "source": "port_check"}]
        result = _merge_port_results(port, "2024-01-01")  # type: ignore[reportArgumentType]
        assert "10.0.0.1" in result
        assert result["10.0.0.1"].mac_address == "aa:bb:cc:dd:ee:ff"

    def test_merge_port_results_empty(self):
        assert _merge_port_results([], "2024-01-01") == {}

    def test_enrich_from_arp_adds_mac(self):
        by_ip = {
            "10.0.0.1": DiscoveredRouter(
                ip_address="10.0.0.1", source="port_check", mac_address=""
            )
        }
        from core.network_probe import _enrich_from_arp  # type: ignore[reportPrivateUsage]

        arp = [{"ip": "10.0.0.1", "mac": "aa:bb:cc:dd:ee:ff"}]
        _enrich_from_arp(arp, by_ip)  # type: ignore[reportArgumentType]
        assert by_ip["10.0.0.1"].mac_address == "aa:bb:cc:dd:ee:ff"

    def test_enrich_from_arp_skips_non_router(self):
        by_ip = {}
        from core.network_probe import _enrich_from_arp  # type: ignore[reportPrivateUsage]

        arp = [{"ip": "10.0.0.5", "mac": "aa:bb:cc:dd:ee:ff"}]
        _enrich_from_arp(arp, by_ip)  # type: ignore[reportArgumentType]
        assert "10.0.0.5" not in by_ip

    def test_enrich_from_arp_skips_if_mac_already_set(self):
        by_ip = {
            "10.0.0.1": DiscoveredRouter(
                ip_address="10.0.0.1", mac_address="11:22:33:44:55:66"
            )
        }
        from core.network_probe import _enrich_from_arp  # type: ignore[reportPrivateUsage]

        arp = [{"ip": "10.0.0.1", "mac": "aa:bb:cc:dd:ee:ff"}]
        _enrich_from_arp(arp, by_ip)  # type: ignore[reportArgumentType]
        assert by_ip["10.0.0.1"].mac_address == "11:22:33:44:55:66"

    def test_full_merge_all_three(self):
        arp = [{"ip": "10.0.0.1", "mac": "aa:bb:cc:dd:ee:ff", "source": "arp"}]
        port = [{"ip": "10.0.0.1", "port": 8728, "source": "port_check"}]
        mndp = [
            {
                "ip": "10.0.0.1",
                "identity": "FullRouter",
                "version": "7.12",
                "board": "RB4011",
                "uptime": "1d 2h",
                "source": "mndp",
                "last_seen": "2024-01-01",
            }
        ]
        result = merge_probe_results(arp, port, mndp)  # type: ignore[reportArgumentType]
        assert len(result) == 1
        r = result[0]
        assert r.identity == "FullRouter"
        assert r.version == "7.12"
        assert r.mac_address == "aa:bb:cc:dd:ee:ff"
        assert "mndp" in r.source
