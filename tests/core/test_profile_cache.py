"""Tests for core/profile_cache.py - TTL cache for profile names."""

import threading
import time
from unittest.mock import patch

from core.profile_cache import ProfileCache


class TestProfileCacheGetSet:
    def test_set_then_get(self):
        cache = ProfileCache(ttl=60)
        cache.set("router1", ["default", "guest"])
        assert cache.get("router1") == ["default", "guest"]

    def test_get_returns_none_for_missing(self):
        cache = ProfileCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_get_returns_copy(self):
        cache = ProfileCache(ttl=60)
        cache.set("r1", ["a"])
        result = cache.get("r1")
        result.append("b")
        assert cache.get("r1") == ["a"]

    def test_set_overwrites_existing(self):
        cache = ProfileCache(ttl=60)
        cache.set("r1", ["old"])
        cache.set("r1", ["new"])
        assert cache.get("r1") == ["new"]


class TestProfileCacheTTL:
    def test_expired_entry_returns_none(self):
        cache = ProfileCache(ttl=0)
        cache.set("r1", ["a"])
        time.sleep(0.01)
        assert cache.get("r1") is None

    def test_fresh_entry_returns_value(self):
        cache = ProfileCache(ttl=10)
        cache.set("r1", ["a"])
        assert cache.get("r1") == ["a"]


class TestProfileCacheInvalidation:
    def test_invalidate_removes_key(self):
        cache = ProfileCache(ttl=60)
        cache.set("r1", ["a"])
        cache.invalidate("r1")
        assert cache.get("r1") is None

    def test_invalidate_nonexistent_key(self):
        cache = ProfileCache(ttl=60)
        cache.invalidate("missing")

    def test_clear_removes_all(self):
        cache = ProfileCache(ttl=60)
        cache.set("r1", ["a"])
        cache.set("r2", ["b"])
        cache.clear()
        assert cache.get("r1") is None
        assert cache.get("r2") is None


class TestProfileCacheMaxSize:
    def test_evicts_lru_when_full(self):
        cache = ProfileCache(ttl=60, max_size=2)
        cache.set("r1", ["a"])
        cache.set("r2", ["b"])
        cache.set("r3", ["c"])
        assert cache.get("r1") is None
        assert cache.get("r2") == ["b"]
        assert cache.get("r3") == ["c"]

    def test_access_refreshes_lru(self):
        cache = ProfileCache(ttl=60, max_size=2)
        cache.set("r1", ["a"])
        cache.set("r2", ["b"])
        cache.get("r1")
        cache.set("r3", ["c"])
        assert cache.get("r1") == ["a"]
        assert cache.get("r2") is None


class TestProfileCacheStats:
    def test_stats_size(self):
        cache = ProfileCache(ttl=60)
        cache.set("r1", ["a"])
        cache.set("r2", ["b"])
        stats = cache.stats()
        assert stats["size"] == 2

    def test_stats_fresh_vs_stale(self):
        # ساعة حتمية: r1 منتهية (فارق > ttl) و r2 جديدة (فارق <= ttl).
        with patch("core.profile_cache.time.time", side_effect=[1000.0, 1000.01, 1000.02]):
            cache = ProfileCache(ttl=0.01)  # type: ignore[reportArgumentType]
            cache.set("r1", ["a"])  # time() -> 1000.0
            cache.set("r2", ["b"])  # time() -> 1000.01
            stats = cache.stats()   # time() -> 1000.02
        assert stats["fresh"] == 1
        assert stats["stale"] == 1


class TestProfileCacheThreadSafety:
    def test_concurrent_set_get(self):
        cache = ProfileCache(ttl=60, max_size=50)
        errors = []

        def writer(key):  # type: ignore[reportMissingParameterType]
            try:
                for i in range(100):
                    cache.set(key, [f"v{i}"])
            except Exception as e:  # noqa: BLE001 - catch-all: log unexpected error before returning result
                errors.append(e)

        def reader(key):  # type: ignore[reportMissingParameterType]
            try:
                for _ in range(100):
                    cache.get(key)
            except Exception as e:  # noqa: BLE001 - catch-all: log unexpected error before returning result
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"r{i}",))
            for i in range(10)
        ] + [
            threading.Thread(target=reader, args=(f"r{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
