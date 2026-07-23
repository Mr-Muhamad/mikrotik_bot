"""Integration tests for core.network_scanner using mocked probes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.network_scanner import discover_routers


def _fake_arp():
    return MagicMock(discover=MagicMock(return_value=[]))


def _fake_port(results=None):
    return MagicMock(discover=AsyncMock(return_value=results or []))


class TestDiscoverRoutersOrchestrator:
    @pytest.mark.asyncio
    async def test_returns_mndp_results(self):
        mndp_entry = {
            "ipv4": "1.2.3.4",
            "mac": "aa:bb:cc:dd:ee:ff",
            "identity": "TestRouter",
            "version": "7.15",
            "board": "RB4011",
        }
        with (
            patch(
                "core.network_scanner.MNDPListenerProbe",
                type(
                    "FakeProbe",
                    (),
                    {
                        "__init__": lambda self, **kw: None,
                        "discover": AsyncMock(return_value=[mndp_entry]),
                    },
                ),
            ),
            patch(
                "core.network_probe.ARPTableProbe",
                lambda: _fake_arp(),
            ),
            patch(
                "core.network_probe.PortScanProbe",
                lambda **kw: _fake_port(),
            ),
        ):
            result = await discover_routers()
        assert len(result) == 1
        assert result[0].ip_address == "1.2.3.4"
        assert result[0].mac_address == "aa:bb:cc:dd:ee:ff"
        assert result[0].source == "mndp"

    @pytest.mark.asyncio
    async def test_empty_mndp_returns_empty(self):
        with (
            patch(
                "core.network_scanner.MNDPListenerProbe",
                type(
                    "FakeProbe",
                    (),
                    {
                        "__init__": lambda self, **kw: None,
                        "discover": AsyncMock(return_value=[]),
                    },
                ),
            ),
            patch(
                "core.network_probe.ARPTableProbe",
                lambda: _fake_arp(),
            ),
            patch(
                "core.network_probe.PortScanProbe",
                lambda **kw: _fake_port(),
            ),
        ):
            result = await discover_routers()
        assert result == []

    @pytest.mark.asyncio
    async def test_progress_callback_invoked(self):
        callback = AsyncMock()
        with (
            patch(
                "core.network_scanner.MNDPListenerProbe",
                type(
                    "FakeProbe",
                    (),
                    {
                        "__init__": lambda self, **kw: None,
                        "discover": AsyncMock(return_value=[]),
                    },
                ),
            ),
            patch(
                "core.network_probe.ARPTableProbe",
                lambda: _fake_arp(),
            ),
            patch(
                "core.network_probe.PortScanProbe",
                lambda **kw: _fake_port(),
            ),
        ):
            await discover_routers(progress_callback=callback)
        assert callback.call_count >= 1
        messages = [c.args[0] for c in callback.await_args_list]
        assert any("MNDP" in msg for msg in messages)
