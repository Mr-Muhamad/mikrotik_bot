"""Unit tests for core/connection_pool.py — ConnectionPool class."""

import time
from unittest.mock import patch, MagicMock

import pytest
from librouteros.exceptions import LibRouterosError

from core.connection_pool import ConnectionPool, MAX_RETRIES
from core.exceptions import RouterNotFoundError


@pytest.fixture
def pool():
    return ConnectionPool()


@pytest.fixture
def fake_api():
    api = MagicMock()
    api.close = MagicMock()
    return api


def _router_db_row(router_id=1, ip="10.0.0.1"):
    return {
        "ip_address": ip, "port": 8728,
        "username": "admin", "password": "pass",
        "identity": f"Router{router_id}",
    }


class TestConnectionPoolInit:
    def test_initial_state(self, pool):
        assert pool.connections == {}
        assert pool.connection_times == {}
        assert pool.router_versions == {}
        assert pool.router_names == {}
        assert pool.total_connection_attempts == 0
        assert pool.successful_connections == 0
        assert pool.failed_connections == 0
        assert pool.cache_hits == 0


class TestRouterInfo:
    def test_invalid_key_raises(self, pool):
        with pytest.raises(RouterNotFoundError, match="not configured"):
            pool.get_router_info("invalid_key")

    def test_nonexistent_id_raises(self, pool):
        with pytest.raises(RouterNotFoundError, match="not found"):
            pool.get_router_info("discovered_99999")


class TestGetConnection:
    def test_first_call_creates_connection(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api) as mock_connect:
            api = pool.get_connection("discovered_1")
            assert api is fake_api
            assert pool.connections["discovered_1"] is fake_api
            assert mock_connect.called

    def test_repeated_calls_use_cache(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api) as mock_connect:
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_1")
            assert mock_connect.call_count == 1
            assert pool.cache_hits == 2


class TestRetry:
    def test_connect_fails_after_max_retries(self, pool):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", side_effect=LibRouterosError("refused")) as mock_connect, \
             patch("core.connection_pool.time.sleep"):
            with pytest.raises(LibRouterosError):
                pool.get_connection("discovered_1")
            assert mock_connect.call_count == 1 + MAX_RETRIES
            assert pool.failed_connections == 1 + MAX_RETRIES

    def test_connect_succeeds_on_retry(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", side_effect=[LibRouterosError("refused"), fake_api]), \
             patch("core.connection_pool.time.sleep"):
            api = pool.get_connection("discovered_1")
            assert api is fake_api
            assert pool.successful_connections == 1
            assert pool.failed_connections == 1


class TestCloseConnection:
    def test_close_removes_from_cache(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool.close_connection("discovered_1")
            assert "discovered_1" not in pool.connections
            fake_api.close.assert_called_once()

    def test_close_nonexistent_does_not_raise(self, pool):
        pool.close_connection("nonexistent")

    def test_close_clears_version_and_name(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool.set_version("discovered_1", "7.15")
            pool.set_cached_name("discovered_1", "MyRouter")
            pool.close_connection("discovered_1")
            assert "discovered_1" not in pool.router_versions
            assert "discovered_1" not in pool.router_names


class TestCleanup:
    def test_cleanup_runs_after_interval(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool._last_cleanup = time.time() - pool._cleanup_interval - 1
            pool.connection_times["discovered_1"] = time.time() - pool._max_connection_age - 1
            pool._maybe_cleanup()
            assert "discovered_1" not in pool.connections

    def test_cleanup_skipped_before_interval(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool._last_cleanup = time.time()
            pool._maybe_cleanup()
            assert "discovered_1" in pool.connections


class TestVersionCache:
    def test_get_version_uninitialized_returns_empty(self, pool):
        assert pool.get_version("discovered_1") == ""

    def test_set_and_get_version(self, pool):
        pool.set_version("discovered_1", "7.15")
        assert pool.get_version("discovered_1") == "7.15"


class TestVersionCache:
    def test_get_version_uninitialized_returns_empty(self, pool):
        assert pool.get_version("discovered_1") == ""

    def test_set_and_get_version(self, pool):
        pool.set_version("discovered_1", "7.15")
        assert pool.get_version("discovered_1") == "7.15"

    def test_invalidate_version(self, pool):
        pool.set_version("discovered_1", "7.15")
        pool.invalidate_version("discovered_1")
        assert pool.get_version("discovered_1") == ""

    def test_invalidate_version_nonexistent_does_not_raise(self, pool):
        pool.invalidate_version("nonexistent")


class TestNameCache:
    def test_get_cached_name_uninitialized(self, pool):
        assert pool.get_cached_name("discovered_1") is None

    def test_set_and_get_cached_name(self, pool):
        pool.set_cached_name("discovered_1", "MyRouter")
        assert pool.get_cached_name("discovered_1") == "MyRouter"

    def test_invalidate_name(self, pool):
        pool.set_cached_name("discovered_1", "MyRouter")
        pool.invalidate_name("discovered_1")
        assert pool.get_cached_name("discovered_1") is None

    def test_invalidate_nonexistent_does_not_raise(self, pool):
        pool.invalidate_name("nonexistent")


class TestMetrics:
    def test_get_metrics_initial(self, pool):
        metrics = pool.get_metrics()
        assert metrics["active_connections"] == 0
        assert metrics["stale_connections"] == 0
        assert metrics["total_attempts"] == 0
        assert metrics["successful"] == 0
        assert metrics["failed"] == 0
        assert metrics["cache_hits"] == 0

    def test_get_metrics_after_connection(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            metrics = pool.get_metrics()
            assert metrics["active_connections"] == 1
            assert metrics["total_attempts"] == 1
            assert metrics["successful"] == 1

    def test_get_metrics_after_cache_hit(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_1")
            metrics = pool.get_metrics()
            assert metrics["cache_hits"] == 1


class TestCloseAll:
    def test_close_all_clears_everything(self, pool, fake_api):
        with patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()), \
             patch("core.connection_pool.connect", return_value=fake_api):
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_2")
            pool.close_all()
            assert len(pool.connections) == 0
