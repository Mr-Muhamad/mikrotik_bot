"""Unit tests for core/connection_pool.py — ConnectionPool class."""

import queue
import time
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api = pool.get_connection("discovered_1")
            assert api is fake_api
            assert "discovered_1" in pool.pools
            assert mock_connect.called

    def test_repeated_calls_use_cache(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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


class TestStaleConnectionHealthCheck:
    """Pooled stale-connection health check with timed executor."""

    def test_healthy_connection_reused(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            api2 = pool.get_connection("discovered_1")

            assert api2 is fake_api
            assert mock_connect.call_count == 1
            assert pool.cache_hits == 1

    def test_stale_librouteros_error_discards_and_reconnects(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            fake_api.path.return_value.side_effect = LibRouterosError("stale")

            pool.get_connection("discovered_1")

            assert mock_connect.call_count == 2
            fake_api.close.assert_called()
            assert pool.active_counts["discovered_1"] == 1

    def test_stale_discard_close_error_ignored(self, pool, fake_api):
        fake_api.close = MagicMock(side_effect=OSError("already closed"))
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            fake_api.path.return_value.side_effect = LibRouterosError("stale")

            api2 = pool.get_connection("discovered_1")

            assert api2 is fake_api
            assert mock_connect.call_count == 2
            assert pool.active_counts["discovered_1"] == 1

    def test_stale_os_error_discards_and_reconnects(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            fake_api.path.return_value.side_effect = OSError("connection reset")

            pool.get_connection("discovered_1")

            assert mock_connect.call_count == 2
            assert pool.active_counts["discovered_1"] == 1

    def test_stale_active_count_decremented_correctly(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            assert pool.active_counts["discovered_1"] == 1

            fake_api.path.return_value.side_effect = LibRouterosError("stale")
            pool.get_connection("discovered_1")

            assert pool.active_counts["discovered_1"] == 1

    def test_health_check_timeout_triggers_reconnect(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api) as mock_connect,
            patch("core.connection_pool._HEALTH_CHECK_TIMEOUT", 0.05),
        ):
            api1 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)

            fake_api.path.return_value.side_effect = lambda *a, **kw: time.sleep(10)

            pool.get_connection("discovered_1")

            assert mock_connect.call_count == 2
            assert pool.active_counts["discovered_1"] == 1

    def test_pool_timeout_raises_timeout_error(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
            patch("queue.Queue.get", side_effect=queue.Empty()),
        ):
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_1")
            pool.get_connection("discovered_1")
            assert pool.active_counts["discovered_1"] == 3

            with pytest.raises(TimeoutError, match="Connection pool timeout"):
                pool.get_connection("discovered_1")


class TestReleaseConnectionEdgeCases:
    def test_release_broken_close_error_logged(self, pool, fake_api):
        fake_api.close = MagicMock(side_effect=LibRouterosError("close failed"))
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
            patch("core.connection_pool.logger.debug") as mock_debug,
        ):
            api = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api, broken=True)
            mock_debug.assert_called()
            assert pool.active_counts["discovered_1"] == 0

    def test_release_connection_queue_full_closes_api(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api1 = pool.get_connection("discovered_1")
            api2 = pool.get_connection("discovered_1")
            api3 = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api1)
            pool.release_connection("discovered_1", api2)
            pool.release_connection("discovered_1", api3)

            pool.release_connection("discovered_1", fake_api)

            assert pool.active_counts["discovered_1"] == 2
            fake_api.close.assert_called()


class TestReconnect:
    def test_reconnect_success(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            api = pool.reconnect("discovered_1")
            assert api is fake_api
            assert pool.active_counts["discovered_1"] == 1

    def test_reconnect_failure_decrements_and_raises(self, pool):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", side_effect=LibRouterosError("refused")),
            patch("core.connection_pool.time.sleep"),
        ):
            with pytest.raises(LibRouterosError):
                pool.reconnect("discovered_1")
            assert pool.active_counts.get("discovered_1", 0) == 0


class TestCloseConnection:
    def test_close_connection_missing_router_returns(self, pool):
        pool.close_connection("discovered_1")

    def test_close_connection_drain_empty_breaks(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
            patch("queue.Queue.get_nowait", side_effect=queue.Empty()),
        ):
            api = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api)
            # Concurrent taker already claimed the item -> get_nowait raises Empty
            pool.close_connection("discovered_1")  # must not raise

    def test_close_connection_close_error_logged(self, pool, fake_api):
        fake_api.close = MagicMock(side_effect=OSError("close error"))
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
            patch("core.connection_pool.logger.debug") as mock_debug,
        ):
            api = pool.get_connection("discovered_1")
            pool.release_connection("discovered_1", api)
            pool.close_connection("discovered_1")
            mock_debug.assert_called()


class TestHasActiveConnection:
    def test_no_connection(self, pool):
        assert pool.has_active_connection("discovered_1") is False

    def test_with_connection(self, pool, fake_api):
        with (
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
            patch("core.connection_pool.connect", return_value=fake_api),
        ):
            pool.get_connection("discovered_1")
            assert pool.has_active_connection("discovered_1") is True
            pool.close_all()
            assert pool.has_active_connection("discovered_1") is False


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
            patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
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
