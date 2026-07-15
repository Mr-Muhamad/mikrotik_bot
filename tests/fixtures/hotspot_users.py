"""Sample hotspot user data for tests — mimics RouterOS API output."""

SAMPLE_HOTSPOT_USERS = [
    {
        ".id": "*1",
        "name": "testuser1",
        "password": "pass123",
        "profile": "default",
        "limit-bytes-total": "1000000000",
        "limit-uptime": "1d",
        "comment": "test batch 1",
        "disabled": "false",
        "bytes-in": "1048576",
        "bytes-out": "2097152",
    },
    {
        ".id": "*2",
        "name": "testuser2",
        "password": "pass456",
        "profile": "vip",
        "limit-bytes-total": "5368709120",
        "limit-uptime": "7d",
        "comment": "vip user",
        "disabled": "false",
        "bytes-in": "1073741824",
        "bytes-out": "536870912",
    },
    {
        ".id": "*3",
        "name": "disabled_user",
        "password": "pass789",
        "profile": "default",
        "limit-bytes-total": "0",
        "limit-uptime": "",
        "comment": "",
        "disabled": "true",
        "bytes-in": "0",
        "bytes-out": "0",
    },
]

SAMPLE_HOTSPOT_PROFILES = [
    {".id": "*1", "name": "default", "shared-users": 1, "rate-limit": ""},
    {".id": "*2", "name": "vip", "shared-users": 2, "rate-limit": "10M/10M"},
]

SAMPLE_HOTSPOT_HOSTS = [
    {
        ".id": "*H1",
        "address": "192.168.88.10",
        "mac-address": "AA:BB:CC:DD:EE:01",
        "user": "testuser1",
    },
    {
        ".id": "*H2",
        "address": "192.168.88.11",
        "mac-address": "AA:BB:CC:DD:EE:02",
        "user": "testuser2",
    },
]

SAMPLE_DHCP_LEASES = [
    {
        ".id": "*L1",
        "address": "192.168.88.10",
        "mac-address": "AA:BB:CC:DD:EE:01",
        "host-name": "Device-One",
    },
    {
        ".id": "*L2",
        "address": "192.168.88.11",
        "mac-address": "AA:BB:CC:DD:EE:02",
        "host-name": "Device-Two",
    },
]

SAMPLE_DISCOVERED_ROUTERS = [
    {
        "id": 1,
        "ip_address": "192.168.88.1",
        "identity": "Main-Router",
        "version": "7.15",
        "board": "RB4011",
        "username": "admin",
        "password": "admin123",
        "port": 8728,
    },
    {
        "id": 2,
        "ip_address": "10.0.0.1",
        "identity": "Branch-Router",
        "version": "6.49",
        "board": "RB750",
        "username": "admin",
        "password": "pass123",
        "port": 8728,
    },
]
