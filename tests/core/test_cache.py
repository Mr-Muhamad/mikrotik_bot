import threading
import time
from unittest.mock import patch

from core.cache import TTLCache


class TestTTLCacheInit:
    def test_default_values(self):
        c = TTLCache()
        assert c._max_size == 100
        assert c._ttl == 3600
        assert len(c) == 0

    def test_custom_values(self):
        c = TTLCache(max_size=5, ttl=10)
        assert c._max_size == 5
        assert c._ttl == 10


class TestTTLCacheSetGet:
    def test_set_and_get(self):
        c = TTLCache()
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_get_missing_key(self):
        c = TTLCache()
        assert c.get("missing") is None

    def test_overwrite_key(self):
        c = TTLCache()
        c.set("k", "old")
        c.set("k", "new")
        assert c.get("k") == "new"

    def test_store_various_types(self):
        c = TTLCache()
        c.set("str", "hello")
        c.set("int", 42)
        c.set("list", [1, 2, 3])
        assert c.get("str") == "hello"
        assert c.get("int") == 42
        assert c.get("list") == [1, 2, 3]


class TestTTLCacheExpiry:
    def test_expired_key_returns_none(self):
        c = TTLCache(ttl=1)
        c.set("k", "v")
        with patch("core.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            assert c.get("k") is None

    def test_valid_key_still_returns_value(self):
        c = TTLCache(ttl=10)
        c.set("k", "v")
        assert c.get("k") == "v"


class TestTTLCacheEviction:
    def test_evicts_oldest_when_full(self):
        c = TTLCache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_get_moves_to_end_for_lru(self):
        c = TTLCache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")
        c.set("c", 3)
        assert c.get("a") == 1
        assert c.get("b") is None


class TestTTLCacheClear:
    def test_clear_removes_all(self):
        c = TTLCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert len(c) == 0
        assert c.get("a") is None


class TestTTLCacheLen:
    def test_len_excludes_expired(self):
        c = TTLCache(ttl=1)
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2
        with patch("core.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            assert len(c) == 0


class TestTTLCacheInvalidate:
    def test_invalidate_removes_key(self):
        c = TTLCache()
        c.set("k", "v")
        c.invalidate("k")
        assert c.get("k") is None

    def test_invalidate_nonexistent_is_safe(self):
        c = TTLCache()
        c.invalidate("nope")


class TestTTLCacheGetKeys:
    def test_get_keys_returns_valid_only(self):
        c = TTLCache(ttl=1)
        c.set("a", 1)
        c.set("b", 2)
        with patch("core.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            c.set("c", 3)
            keys = c.get_keys()
        assert keys == ["c"]


class TestTTLCacheThreadSafety:
    def test_concurrent_set_get(self):
        c = TTLCache(max_size=50, ttl=60)
        errors = []

        def writer():
            try:
                for i in range(100):
                    c.set(f"key-{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    c.get(f"key-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
