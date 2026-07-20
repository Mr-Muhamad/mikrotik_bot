"""Network probe abstractions for router discovery.

This module provides pluggable discovery strategies (ARP, MNDP, port scan)
that can be tested independently. The orchestrator lives in
``core/network_scanner.py`` and composes these probes.

Why a Protocol? Each probe has different transport semantics:
- ARPTableProbe is sync (reads OS arp table via subprocess)
- PortScanProbe is async (uses asyncio.open_connection)
- MNDPListenerProbe is async (raw UDP socket)

A Protocol lets us swap implementations for tests without inheritance.
"""

import asyncio
import logging
import platform
import re
import socket
import struct
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from config import DEFAULT_API_PORT

logger = logging.getLogger(__name__)


# ─── MNDP protocol constants ───────────────────────────────────

MNDP_TYPE_MAC = 1
MNDP_TYPE_IDENTITY = 5
MNDP_TYPE_VERSION = 7
MNDP_TYPE_PLATFORM = 8
MNDP_TYPE_UPTIME = 10
MNDP_TYPE_SOFTWARE_ID = 11
MNDP_TYPE_BOARD = 12
MNDP_TYPE_INTERFACE_NAME = 16
MNDP_TYPE_IPV4 = 17
MNDP_PORT = 5678
MNDP_DISCOVERY_PAYLOAD = bytes([0x00, 0x00, 0x00, 0x00])


# ─── Pure helper functions (no I/O) ───────────────────────────


def decode_mndp_packet(data: bytes) -> dict[str, str]:
    """Decode a single MNDP packet payload into a dict of attributes.

    Returns keys: mac, identity, version, platform, software_id, board,
    interface_name, uptime, ipv4. Missing attributes are absent from the dict.
    """
    parts: dict[str, str] = {}
    if len(data) < 4:
        return parts
    breader = memoryview(data)[4:]
    type_map = {
        MNDP_TYPE_IDENTITY: "identity",
        MNDP_TYPE_VERSION: "version",
        MNDP_TYPE_PLATFORM: "platform",
        MNDP_TYPE_SOFTWARE_ID: "software_id",
        MNDP_TYPE_BOARD: "board",
        MNDP_TYPE_INTERFACE_NAME: "interface_name",
    }
    while len(breader) >= 4:
        part_type = struct.unpack(">H", breader[:2])[0]
        breader = breader[2:]
        length = struct.unpack(">H", breader[:2])[0]
        breader = breader[2:]
        if length > len(breader):
            break
        payload = breader[:length]
        breader = breader[length:]
        if part_type == MNDP_TYPE_MAC:
            parts["mac"] = ":".join(f"{x:02x}" for x in payload)
        elif part_type in type_map:
            try:
                value = bytes(payload).decode("utf-8", errors="replace")
                parts[type_map[part_type]] = value
            except (UnicodeDecodeError, AttributeError) as e:
                logger.debug(f"Failed to decode MNDP part {part_type}: {e}")
        elif part_type == MNDP_TYPE_UPTIME and len(payload) >= 4:
            seconds = struct.unpack("<I", bytes(payload[:4]))[0]
            days, remainder = divmod(seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, _ = divmod(remainder, 60)
            parts["uptime"] = f"{days}d {hours}h {minutes}m"
        elif part_type == MNDP_TYPE_IPV4:
            try:
                parts["ipv4"] = socket.inet_ntop(socket.AF_INET, bytes(payload))
            except (OSError, ValueError) as e:
                logger.debug(f"Failed to parse ipv4 in MNDP: {e}")
    return parts


def parse_arp_table_windows(output: str) -> dict[str, str]:
    """Parse ``arp -a`` output on Windows.

    Returns ``{ip: mac}`` for dynamic entries (excluding zero MAC).
    """
    entries: dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        match = re.match(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})", line)
        if not match:
            continue
        ip = match.group(1)
        mac = match.group(2).replace("-", ":").lower()
        if mac != "00:00:00:00:00:00" and "dynamic" in line.lower():
            entries[ip] = mac
    return entries


def parse_arp_table_linux(output: str) -> dict[str, str]:
    """Parse ``ip neigh`` output on Linux.

    Returns ``{ip: mac}`` for valid entries (excluding zero MAC).
    """
    entries: dict[str, str] = {}
    for line in output.splitlines():
        parts_line = line.split()
        if len(parts_line) < 5:
            continue
        ip = parts_line[0]
        mac = parts_line[4].lower()
        if re.match(r"[0-9a-fA-F:]{17}", mac) and mac != "00:00:00:00:00:00":
            entries[ip] = mac
    return entries


# ─── Probe Protocol ────────────────────────────────────────────


@runtime_checkable
class NetworkProbe(Protocol):
    """A discovery strategy that yields IP candidates or full router metadata.

    Implementations may be sync (ARP table) or async (MNDP, port scan).
    The scanner orchestrator awaits the result if it's a coroutine.
    """

    def discover(self) -> list[dict]: ...


# ─── DiscoveredRouter dataclass (moved from network_scanner) ───


@dataclass
class DiscoveredRouter:
    """Represents a MikroTik router discovered on the network."""

    ip_address: str
    mac_address: str = ""
    identity: str = "Unknown"
    version: str = ""
    board: str = ""
    software_id: str = ""
    platform: str = "MikroTik"
    uptime: str = ""
    interface_name: str = ""
    port: int = DEFAULT_API_PORT
    username: str = ""
    password: str = ""
    last_seen: str = ""
    source: str = ""
    db_id: int | None = None

    def display_name(self) -> str:
        """Return a short name string with identity, version, and board."""
        name = self.identity if self.identity != "Unknown" else self.ip_address
        parts = [name]
        if self.version:
            parts.append(f"v{self.version}")
        if self.board:
            parts.append(self.board)
        return " - ".join(parts)

    def display_line(self) -> str:
        """Return a formatted multi-line display string with status emoji."""
        status_emoji = "🟢" if self.version else "🟡"
        line = f"{status_emoji} {self.identity}"
        if self.version:
            line += f" v{self.version}"
        if self.board:
            line += f" | {self.board}"
        if self.uptime:
            line += f" | ⏱ {self.uptime}"
        line += f"\n   📍 {self.ip_address}:{self.port}"
        return line


# ─── Concrete probes ───────────────────────────────────────────


class ARPTableProbe:
    """Reads the OS ARP table to discover IP/MAC pairs on the local network.

    Sync probe (uses ``subprocess.run`` to call ``arp -a`` or ``ip neigh``).
    Inject ``run_fn`` to override subprocess behavior in tests.
    """

    def __init__(self, run_fn=subprocess.run, system: str | None = None) -> None:
        self._run = run_fn
        self._system = system or platform.system()

    def discover(self) -> list[dict]:
        """Return ``[{ip, mac, source}]`` for each dynamic ARP entry."""
        try:
            if self._system == "Windows":
                result = self._run(["arp", "-a"], capture_output=True, text=True, timeout=10)
                entries = parse_arp_table_windows(result.stdout)
            elif self._system == "Linux":
                result = self._run(["ip", "neigh"], capture_output=True, text=True, timeout=10)
                entries = parse_arp_table_linux(result.stdout)
            else:
                logger.info(f"ARP table probe not supported on {self._system}")
                return []
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to parse ARP table: {e}")
            return []
        return [{"ip": ip, "mac": mac, "source": "arp"} for ip, mac in entries.items()]


class PortScanProbe:
    """Async probe that tests TCP connectivity on the MikroTik API port (8728).

    Inject ``open_connection`` to override asyncio behavior in tests.
    """

    def __init__(
        self,
        ips: list[str],
        port: int = DEFAULT_API_PORT,
        timeout: float = 2.0,
        open_connection=asyncio.open_connection,
    ) -> None:
        self._ips = list(ips)
        self._port = port
        self._timeout = timeout
        self._open_connection = open_connection

    async def discover(self) -> list[dict]:
        """Return ``[{ip, port, source}]`` for IPs that accept TCP connections."""
        if not self._ips:
            return []
        results = await asyncio.gather(
            *(self._check_one(ip) for ip in self._ips),
            return_exceptions=False,
        )
        return [
            {"ip": ip, "port": self._port, "source": "port_check"}
            for ip, is_open in zip(self._ips, results, strict=False)
            if is_open
        ]

    async def _check_one(self, ip: str) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                self._open_connection(ip, self._port),
                timeout=self._timeout,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                # Broad catch: may be closed already, mock objects in tests,
                # or other StreamWriter edge cases. This is just cleanup.
                pass
            return True
        except (TimeoutError, ConnectionRefusedError, OSError):
            return False


def _get_local_ips() -> set[str]:
    """Return a set of local IPv4 addresses for self-echo filtering.

    When we broadcast to 255.255.255.255:5678, the OS delivers a copy back
    to our own socket.  We must filter these out so they are not treated as
    neighbor responses.
    """
    local_ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            local_ips.add(addr if isinstance(addr, str) else str(addr))
    except (OSError, socket.gaierror):
        pass
    local_ips.add("127.0.0.1")
    return local_ips


class MNDPListenerProbe:
    """Async probe that broadcasts MNDP discovery packets and listens for replies.

    Uses a **single socket** for both sending and receiving to avoid the
    race condition where replies are lost before the listener binds.
    Sends multiple refresh packets during the listen window (matching
    WinBox behavior) for higher reliability.

    Inject ``socket_factory`` to override raw socket creation in tests.
    The factory must return a socket-like object with the same interface
    as ``socket.socket``.
    """

    SEND_INTERVAL = 5.0  # seconds between refresh broadcasts

    def __init__(
        self,
        timeout: float = 10.0,
        socket_factory=None,
    ) -> None:
        self._timeout = timeout
        self._socket_factory = socket_factory or socket.socket

    async def discover(self) -> list[dict]:
        """Return ``[{ip, source, last_seen, ...attributes}]`` for each MNDP reply.

        Raises:
            PermissionError: If the OS denies raw UDP socket access.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._discover_sync)

    def _discover_sync(self) -> list[dict]:
        """Single-socket send+listen cycle (runs in executor thread)."""

        discovered: dict[str, dict] = {}
        local_ips = _get_local_ips()
        sock = None

        try:
            sock = self._socket_factory(
                socket.AF_INET,
                socket.SOCK_DGRAM,
                socket.IPPROTO_UDP,
            )
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # SO_REUSEADDR is required on Windows; SO_REUSEPORT on POSIX
            # so we can coexist with WinBox or another MNDP listener.
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", MNDP_PORT))
            sock.settimeout(1.0)

            start_time = time.time()
            last_send = 0.0
            logger.info(f"MNDP single-socket discovery started (timeout: {self._timeout}s)")

            while time.time() - start_time <= self._timeout:
                now = time.time()

                # Send a refresh broadcast every SEND_INTERVAL seconds.
                # The first one goes out immediately.
                if now - last_send >= self.SEND_INTERVAL:
                    try:
                        sock.sendto(MNDP_DISCOVERY_PAYLOAD, ("255.255.255.255", MNDP_PORT))
                        last_send = now
                        logger.debug("MNDP refresh packet sent")
                    except OSError as send_err:
                        logger.error(f"Failed to send MNDP refresh: {send_err}")

                # Receive with 1-second timeout so we can re-send periodically.
                try:
                    data, addr = sock.recvfrom(65535)
                    ip = addr[0]

                    # Self-echo filter: ignore packets from our own IPs.
                    if ip in local_ips:
                        continue

                    parts = decode_mndp_packet(data)
                    if "identity" not in parts and "board" not in parts:
                        continue

                    if ip not in discovered:
                        discovered[ip] = {
                            "ip": ip,
                            "source": "mndp",
                            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    router = discovered[ip]
                    router["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for key in (
                        "mac",
                        "identity",
                        "version",
                        "platform",
                        "board",
                        "software_id",
                        "uptime",
                        "interface_name",
                    ):
                        if key in parts and parts[key]:
                            router[key] = parts[key]
                    if "ipv4" in parts and parts["ipv4"]:
                        router["ip"] = parts["ipv4"]
                except TimeoutError:
                    continue
                except OSError as e:
                    logger.error(f"MNDP recv error: {e}")
                    continue

        except PermissionError as e:
            logger.warning(f"MNDP requires admin privileges (run as Administrator): {e}")
            raise
        except OSError as e:
            logger.error(f"Failed to start MNDP listener: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        logger.info(f"MNDP single-socket discovery finished: {len(discovered)} devices")
        return list(discovered.values())


# ─── Orchestrator helper ───────────────────────────────────────


def merge_probe_results(
    arp_results: list[dict],
    port_results: list[dict],
    mndp_results: list[dict],
) -> list[DiscoveredRouter]:
    """Merge candidate dicts from the three probes into a deduplicated list of routers.

    Priority order (highest first):
    1. MNDP (richest metadata)
    2. Port scan (proves API reachable)
    3. ARP table (just IP/MAC)
    """
    by_ip: dict[str, DiscoveredRouter] = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for entry in port_results:
        ip = entry["ip"]
        by_ip[ip] = DiscoveredRouter(
            ip_address=ip,
            mac_address=entry.get("mac", ""),
            source="port_check",
            last_seen=now,
        )

    for entry in arp_results:
        ip = entry["ip"]
        if ip in by_ip:
            by_ip[ip].mac_address = entry.get("mac", by_ip[ip].mac_address)
            by_ip[ip].source = "arp+port"
        else:
            by_ip[ip] = DiscoveredRouter(
                ip_address=ip,
                mac_address=entry.get("mac", ""),
                source="arp",
                last_seen=now,
            )

    for entry in mndp_results:
        ip = entry["ip"]
        if ip in by_ip:
            existing = by_ip[ip]
            existing.source = f"mndp+{existing.source}" if "port" in existing.source else "mndp"
            existing.last_seen = entry.get("last_seen", existing.last_seen)
            for attr in (
                "identity",
                "version",
                "board",
                "software_id",
                "platform",
                "uptime",
                "interface_name",
            ):
                val = entry.get(attr, "")
                if val and (not getattr(existing, attr) or getattr(existing, attr) == "Unknown"):
                    setattr(existing, attr, val)
        else:
            router = DiscoveredRouter(
                ip_address=ip,
                source="mndp",
                last_seen=entry.get("last_seen", now),
            )
            for attr in (
                "mac_address",
                "identity",
                "version",
                "board",
                "software_id",
                "platform",
                "uptime",
                "interface_name",
            ):
                key = attr if attr != "mac_address" else "mac"
                if entry.get(key):
                    setattr(router, attr, entry[key])
            by_ip[ip] = router

    return list(by_ip.values())
