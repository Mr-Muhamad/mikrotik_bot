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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from config import DEFAULT_API_PORT
from core.mikrotik_client import RouterOSRow

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
                logger.debug("Failed to decode MNDP part %s: %s", part_type, e)
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
                logger.debug("Failed to parse ipv4 in MNDP: %s", e)
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

    def discover(self) -> list[RouterOSRow]: ...


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
        status_emoji = "🟢" if self.version else "🌐"
        if self.identity and self.identity != "Unknown":
            name = self.identity
        else:
            name = f"راوتر MikroTik ({self.ip_address})"
        line = f"{status_emoji} {name}"
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

    def __init__(
        self,
        run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        system: str | None = None,
    ) -> None:
        self._run = run_fn
        self._system = system or platform.system()

    def discover(self) -> list[RouterOSRow]:
        """Return ``[{ip, mac, source}]`` for each dynamic ARP entry."""
        try:
            if self._system == "Windows":
                result = self._run(["arp", "-a"], capture_output=True, text=True, timeout=10)
                entries = parse_arp_table_windows(result.stdout)
            elif self._system == "Linux":
                result = self._run(["ip", "neigh"], capture_output=True, text=True, timeout=10)
                entries = parse_arp_table_linux(result.stdout)
            else:
                logger.info("ARP table probe not supported on %s", self._system)
                return []
        except (PermissionError, OSError, subprocess.TimeoutExpired) as e:
            logger.error(
                "Failed to parse ARP table (error type: %s): %s",
                type(e).__name__, e,
            )
            return []
        except Exception as e:  # noqa: BLE001
            logger.exception(
                "Failed to parse ARP table (error type: %s): %s",
                type(e).__name__, e,
            )
            return []
        return [{"ip": ip, "mac": mac, "source": "arp"} for ip, mac in entries.items()]


_OpenConnFn = Callable[
    ..., Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]
]


class PortScanProbe:
    """Async probe that tests TCP connectivity on the MikroTik API port (8728).

    Inject ``open_connection`` to override asyncio behavior in tests.
    """

    def __init__(
        self,
        ips: list[str],
        port: int = DEFAULT_API_PORT,
        timeout: float = 2.0,
        open_connection: _OpenConnFn = asyncio.open_connection,
    ) -> None:
        self._ips = list(ips)
        self._port = port
        self._timeout = timeout
        self._open_connection = open_connection

    async def discover(self) -> list[RouterOSRow]:
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
            except Exception:  # noqa: S110, BLE001
                # Broad catch: may be closed already, mock objects in tests,
                # or other StreamWriter edge cases. This is just cleanup.
                pass
            return True
        except Exception:  # noqa: BLE001
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
        socket_factory: Callable[..., socket.socket] | None = None,
    ) -> None:
        self._timeout = timeout
        self._socket_factory = socket_factory or socket.socket

    async def discover(self) -> list[RouterOSRow]:
        """Return ``[{ip, source, last_seen, ...attributes}]`` for each MNDP reply.

        Raises:
            PermissionError: If the OS denies raw UDP socket access.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._discover_sync)

    def _setup_socket(self) -> socket.socket:
        """Create, configure, and bind the MNDP UDP socket."""
        sock = self._socket_factory(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP,
        )
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        so_reuse_port = getattr(socket, "SO_REUSEPORT", None)
        if so_reuse_port is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, so_reuse_port, 1)
            except OSError:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", MNDP_PORT))
        sock.settimeout(1.0)
        return sock

    def _send_broadcast(self, sock: socket.socket, last_send: float) -> float:
        """Send an MNDP broadcast packet if the send interval has elapsed.

        Returns the updated ``last_send`` timestamp.
        """
        now = time.time()
        if now - last_send >= self.SEND_INTERVAL:
            try:
                sock.sendto(MNDP_DISCOVERY_PAYLOAD, ("255.255.255.255", MNDP_PORT))
                last_send = now
                logger.debug("MNDP refresh packet sent")
            except OSError as send_err:
                logger.error("Failed to send MNDP refresh: %s", send_err)
        return last_send

    def _process_packet(
        self,
        data: bytes,
        ip: str,
        local_ips: set[str],
        discovered: dict[str, RouterOSRow],
    ) -> None:
        """Process a single received MNDP packet and update ``discovered``."""
        if ip in local_ips:
            return
        parts = decode_mndp_packet(data)
        if "identity" not in parts and "board" not in parts:
            return
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

    def _discover_sync(self) -> list[RouterOSRow]:
        """Single-socket send+listen cycle (runs in executor thread)."""
        discovered: dict[str, RouterOSRow] = {}
        local_ips = _get_local_ips()
        sock = None

        try:
            sock = self._setup_socket()
            start_time = time.time()
            last_send = 0.0
            logger.info("MNDP single-socket discovery started (timeout: %ss)", self._timeout)

            while time.time() - start_time <= self._timeout:
                last_send = self._send_broadcast(sock, last_send)
                try:
                    data, addr = sock.recvfrom(65535)
                    self._process_packet(data, addr[0], local_ips, discovered)
                except TimeoutError:
                    continue
                except OSError as e:
                    logger.error("MNDP recv error: %s", e)
                    continue

        except PermissionError as e:
            logger.warning("MNDP requires admin privileges (run as Administrator): %s", e)
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to start MNDP listener (error type: %s): %s",
                type(e).__name__, e,
            )
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        logger.info("MNDP single-socket discovery finished: %d devices", len(discovered))
        return list(discovered.values())


# ─── Orchestrator helper ───────────────────────────────────────


_MNDP_ATTRS = (
    "identity",
    "version",
    "board",
    "software_id",
    "platform",
    "uptime",
    "interface_name",
)
_MNDP_ATTRS_WITH_MAC = ("mac_address",) + _MNDP_ATTRS


def _merge_port_results(
    port_results: list[RouterOSRow],
    now: str,
) -> dict[str, DiscoveredRouter]:
    """Index verified routers (open API port 8728) by IP."""
    by_ip: dict[str, DiscoveredRouter] = {}
    for entry in port_results:
        ip = str(entry["ip"])
        by_ip[ip] = DiscoveredRouter(
            ip_address=ip,
            mac_address=str(entry.get("mac", "")),
            source="port_check",
            last_seen=now,
        )
    return by_ip


def _merge_mndp_results(
    mndp_results: list[RouterOSRow],
    by_ip: dict[str, DiscoveredRouter],
    now: str,
) -> None:
    """Add or enrich entries with MNDP discovery data (richest metadata)."""
    for entry in mndp_results:
        ip = str(entry.get("ipv4") or entry.get("ip", ""))
        if not ip:
            continue
        if ip in by_ip:
            existing = by_ip[ip]
            existing.source = f"mndp+{existing.source}" if "port" in existing.source else "mndp"
            existing.last_seen = str(entry.get("last_seen", existing.last_seen))
            for attr in _MNDP_ATTRS:
                val = entry.get(attr, "")
                if val and (not getattr(existing, attr) or getattr(existing, attr) == "Unknown"):
                    setattr(existing, attr, str(val))
        else:
            router = DiscoveredRouter(
                ip_address=ip,
                source="mndp",
                last_seen=str(entry.get("last_seen", now)),
            )
            for attr in _MNDP_ATTRS_WITH_MAC:
                key = attr if attr != "mac_address" else "mac"
                if entry.get(key):
                    setattr(router, attr, str(entry[key]))
            by_ip[ip] = router


def _enrich_from_arp(
    arp_results: list[RouterOSRow],
    by_ip: dict[str, DiscoveredRouter],
) -> None:
    """Enrich MAC addresses from ARP table ONLY for confirmed routers."""
    for entry in arp_results:
        ip = entry.get("ip")
        if ip and ip in by_ip:
            if not by_ip[ip].mac_address and entry.get("mac"):
                by_ip[ip].mac_address = entry["mac"]  # type: ignore[reportAttributeAccessIssue]
            if "mndp" not in by_ip[ip].source:
                by_ip[ip].source = "arp+port"


def merge_probe_results(
    arp_results: list[RouterOSRow],
    port_results: list[RouterOSRow],
    mndp_results: list[RouterOSRow],
) -> list[DiscoveredRouter]:
    """Merge candidate dicts from the three probes into a deduplicated list of routers.

    Priority & Validation:
    1. MNDP: Guaranteed MikroTik router (richest metadata).
    2. Port scan: Verified MikroTik API port (8728) reachable.
    3. ARP table: Used ONLY to enrich MAC addresses for verified routers. Plain ARP
       entries without open API port (8728) or MNDP response are ignored (non-router LAN devices).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_ip = _merge_port_results(port_results, now)
    _merge_mndp_results(mndp_results, by_ip, now)
    _enrich_from_arp(arp_results, by_ip)
    return list(by_ip.values())
