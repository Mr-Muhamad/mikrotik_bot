"""Contract test: the MikroTik singleton must satisfy the MikrotikClient Protocol.

Guards against signature/method drift between MikrotikAPI and the Protocol
that domain managers depend on. runtime_checkable verifies method presence.
"""

from core.mikrotik_api import MikrotikAPI, mikrotik_api
from core.mikrotik_client import MikrotikClient


def test_singleton_satisfies_protocol():
    assert isinstance(mikrotik_api, MikrotikClient)


def test_class_instance_satisfies_protocol():
    assert isinstance(MikrotikAPI(), MikrotikClient)


def test_managers_default_to_protocol_client():
    from core.hotspot_manager import HotspotManager
    from core.profile_sync import ProfileSync
    from core.stats import StatsManager
    from core.userman_manager import UserManager

    for manager in (HotspotManager(), UserManager(), ProfileSync(), StatsManager()):
        assert isinstance(manager._api, MikrotikClient)
