"""Tests for core.router_key.RouterKey."""

from unittest.mock import patch

from core.router_key import RouterKey


class TestRouterKeyDiscovered:
    @patch("core.router_key.ROUTER_KEY_PREFIX", "discovered_")
    def test_creates_discovered_key(self):
        key = RouterKey.discovered(5)
        assert str(key) == "discovered_5"
        assert key.db_id == 5
        assert key.is_discovered()

    @patch("core.router_key.ROUTER_KEY_PREFIX", "discovered_")
    def test_db_id_from_raw(self):
        key = RouterKey("discovered_42")
        assert key.db_id == 42
        assert key.is_discovered()


class TestRouterKeyLegacy:
    @patch("core.router_key.ROUTER_KEY_PREFIX", "discovered_")
    def test_legacy_key_no_db_id(self):
        key = RouterKey("router1")
        assert str(key) == "router1"
        assert key.db_id is None
        assert not key.is_discovered()


class TestRouterKeyParsing:
    @patch("core.router_key.ROUTER_KEY_PREFIX", "discovered_")
    def test_parse_creates_key(self):
        key = RouterKey.parse("discovered_10")
        assert key.db_id == 10

    @patch("core.router_key.ROUTER_KEY_PREFIX", "discovered_")
    def test_invalid_discovered_id(self):
        key = RouterKey("discovered_abc")
        assert key.db_id is None
        assert not key.is_discovered()


class TestRouterKeyEquality:
    def test_eq_router_key(self):
        a = RouterKey("discovered_1")
        b = RouterKey("discovered_1")
        assert a == b

    def test_eq_string(self):
        key = RouterKey("discovered_1")
        assert key == "discovered_1"
        assert key != "other"

    def test_ne_other_type(self):
        key = RouterKey("discovered_1")
        assert key != 42

    def test_hash_consistent(self):
        a = RouterKey("discovered_1")
        b = RouterKey("discovered_1")
        assert hash(a) == hash(b)
        assert hash(a) == hash("discovered_1")

    def test_usable_in_set(self):
        s = {RouterKey("discovered_1"), RouterKey("discovered_1")}
        assert len(s) == 1


class TestRouterKeyRepr:
    def test_repr(self):
        key = RouterKey("discovered_1")
        assert repr(key) == "RouterKey('discovered_1')"


class TestRouterKeySlots:
    def test_no_dict(self):
        key = RouterKey("x")
        assert not hasattr(key, "__dict__")


class TestRouterKeyRaw:
    def test_raw_property(self):
        key = RouterKey("discovered_3")
        assert key.raw == "discovered_3"
