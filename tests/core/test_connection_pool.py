"""Unit tests for core/connection_pool.py — ConnectionPool class."""

from unittest.mock import MagicMock, patch

import pytest
from librouteros.exceptions import LibRouterosError

from core.connection_pool import MAX_RETRIES, ConnectionPool
from core.exceptions import RouterNotFoundError


@pytest.fixture
def pool():
    p = ConnectionPool()
    yield p
    p.close_all()


@pytest.fixture
def fake_api():
    api = MagicMock()
    api.close = MagicMock()
    return api


def _router_db_row(router_id=1, ip="10.0.0.1"):
    return {
        "ip_address": ip,
        "port": 8728,
        "username": "admin",
        "password": "pass",
        "identity": f"Router{router_id}",
    }


class TestConnectionPoolInit:
    def test_initial_state(self, pool):
        assert pool.pools == {}
        assert pool.active_counts == {}
        assert len(pool.router_versions) == 0
        assert len(pool.router_names) == 0
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
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api = pool.get_connection("discovered_1")
            assert api is fake_api
            assert "discovered_1" in pool.pools
            assert mock_connect.called

    def test_repeated_calls_use_cache(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            api2 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api2)

            api3 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api3)

            assert mock_connect.call_count == 1
            assert pool.cache_hits == 2


class TestRetry:
    def test_connect_fails_after_max_retries(self, pool):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch(
                "core.connection_pool.connect", side_effect=LibRouterosError("refused")
            ) as mock_connect,
            patch("core.connection_pool.time.sleep"),
        ):
            with pytest.raises(LibRouterosError):
                pool.get_connection("discovered_1")
            assert mock_connect.call_count == 1 + MAX_RETRIES
            assert pool.failed_connections == 1 + MAX_RETRIES

    def test_connect_succeeds_on_retry(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch(
                "core.connection_pool.connect",
                side_effect=[LibRouterosError("refused"), fake_api],
            ),
            patch("core.connection_pool.time.sleep"),
        ):
            api = pool.get_connection("discovered_1")
            assert api is fake_api
            assert pool.successful_connections == 1
            assert pool.failed_connections == 1


class TestReleaseConnection:
    def test_release_connection_adds_to_queue(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api = pool.get_connection("discovered_1")
            q = pool.pools["discovered_1"]
            assert q.empty()

            pool.release_connection("discovered_1", api)
            assert not q.empty()
            assert pool.active_counts["discovered_1"] == 1

    def test_release_broken_connection_closes_and_discards(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api, broken=True)

            fake_api.close.assert_called_once()
            q = pool.pools["discovered_1"]
            assert q.empty()
            assert pool.active_counts["discovered_1"] == 0


class TestCloseAll:
    def test_close_all_clears_everything(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            api2 = pool.get_connection("discovered_2")
            pool.release_connection("discovered_2", api2)

            pool.close_all()
            metrics = pool.get_metrics()
            assert metrics["idle_connections"] == 0
            assert metrics["active_connections"] == 0
            assert fake_api.close.call_count == 2


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


class TestMetrics:
    def test_get_metrics_initial(self, pool):
        metrics = pool.get_metrics()
        assert metrics["total_attempts"] == 0
        assert metrics["successful"] == 0
        assert metrics["failed"] == 0
        assert "idle_connections" in metrics
        assert "active_connections" in metrics
        assert metrics["idle_connections"] == 0
        assert metrics["active_connections"] == 0

    def test_get_metrics_after_connection(self, pool, fake_api):
        with (
            patch("core.connection_pool.get_router_by_id", return_value=_router_db_row()),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api = pool.get_connection("discovered_1")
            metrics = pool.get_metrics()
            assert metrics["total_attempts"] == 1
            assert metrics["active_connections"] == 1
            assert metrics["idle_connections"] == 0

            pool.release_connection("discovered_1", api)
            metrics2 = pool.get_metrics()
            assert metrics2["active_connections"] == 1
            assert metrics2["idle_connections"] == 1
