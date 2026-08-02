"""Deterministic concurrency stress tests for router connection paths.

These tests use barriers and fully mocked external I/O so behaviour is
reproducible on every run (no timing-dependent sleeps or real sockets).
"""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from librouteros.exceptions import LibRouterosError

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from core.connection_pool import ConnectionPool
from core.mikrotik_api import MikrotikAPI


def _router_db_row(router_id: int = 1, ip: str = "10.0.0.1") -> dict[str, object]:
    return {
        "ip_address": ip,
        "port": 8728,
        "username": "admin",
        "password": "pass",
        "identity": f"Router{router_id}",
    }


class TestHalfOpenConcurrency:
    def test_open_to_half_open_allows_single_trial_under_concurrency(self):
        clock = [1000.0]
        breaker = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)
        breaker._state["router-fault-1"] = CircuitState.OPEN
        breaker._last_failure_time["router-fault-1"] = clock[0] - 31.0

        n_threads = 16
        barrier = threading.Barrier(n_threads)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def worker() -> None:
            try:
                barrier.wait(timeout=10)
                breaker.before_request("router-fault-1")
                outcome = "allowed"
            except CircuitBreakerOpenError:
                outcome = "blocked"
            with outcomes_lock:
                outcomes.append(outcome)

        # IMPORTANT: the clock patch is entered/exited ONLY on the main thread and
        # wraps the whole executor block. unittest.mock.patch is not thread-safe when
        # multiple threads enter/exit the SAME global target concurrently: overlapping
        # enter/exit restores a stale mock, permanently replacing the global
        # time.monotonic (all event loops created afterwards freeze -> pytest hang).
        # The clock is constant (clock[0] never changes) so a single shared mock is
        # equivalent for all workers.
        with (
            ThreadPoolExecutor(max_workers=n_threads) as executor,
            patch("core.circuit_breaker.time.monotonic", return_value=clock[0]),
        ):
            futures = [executor.submit(worker) for _ in range(n_threads)]
            for future in futures:
                future.result(timeout=15)

        assert outcomes.count("allowed") == 1
        assert outcomes.count("blocked") == n_threads - 1
        assert breaker.get_state("router-fault-1") is CircuitState.HALF_OPEN
        assert breaker._in_trial["router-fault-1"] is True


class TestConnectionPoolCeiling:
    def test_max_connections_per_router_enforced_under_concurrency(self):
        pool = ConnectionPool()
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def worker() -> None:
            try:
                barrier.wait(timeout=10)
                pool.get_connection("discovered_1")
                outcome = "ok"
            except TimeoutError:
                outcome = "timeout"
            with outcomes_lock:
                outcomes.append(outcome)

        try:
            with (
                patch("database.models.get_router_by_id", return_value=_router_db_row(), create=True),
                patch(
                    "core.connection_pool.connect",
                    side_effect=lambda *args, **kwargs: MagicMock(),
                ) as mock_connect,
                patch("queue.Queue.get", side_effect=queue.Empty()),
            ):
                with ThreadPoolExecutor(max_workers=n_threads) as executor:
                    futures = [executor.submit(worker) for _ in range(n_threads)]
                    for future in futures:
                        future.result(timeout=15)

                assert pool.active_counts["discovered_1"] == 3
                assert mock_connect.call_count == 3
        finally:
            pool.close_all()

        assert outcomes.count("ok") == 3
        assert outcomes.count("timeout") == n_threads - 3


class TestRetryStormShortCircuit:
    def test_concurrent_requests_short_circuit_after_open(self):
        api = MikrotikAPI()
        api._circuit_breaker = CircuitBreaker(failure_threshold=1, reset_timeout=30.0)
        fake_connection = MagicMock()

        with (
            patch.object(api._pool, "get_connection", return_value=fake_connection) as mock_get,
            patch.object(api._pool, "reconnect", return_value=fake_connection) as mock_reconnect,
            patch.object(
                api, "_call_command", side_effect=LibRouterosError("connection reset")
            ) as mock_call,
            patch("core.mikrotik_api.time.sleep"),
        ):
            with pytest.raises(LibRouterosError):
                api._execute_with_retry("router-storm-1", "ip/hotspot/active/print", 30)

            assert mock_call.call_count == 3
            assert mock_get.call_count == 1
            assert mock_reconnect.call_count == 2
            assert api._circuit_breaker.get_state("router-storm-1") is CircuitState.OPEN

            n_threads = 12
            barrier = threading.Barrier(n_threads)
            outcomes: list[str] = []
            outcomes_lock = threading.Lock()

            def worker() -> None:
                try:
                    barrier.wait(timeout=10)
                    api._execute_with_retry("router-storm-1", "ip/hotspot/active/print", 30)
                    outcome = "ran"
                except CircuitBreakerOpenError:
                    outcome = "short-circuited"
                with outcomes_lock:
                    outcomes.append(outcome)

            with ThreadPoolExecutor(max_workers=n_threads) as executor:
                futures = [executor.submit(worker) for _ in range(n_threads)]
                for future in futures:
                    future.result(timeout=15)

            assert outcomes.count("short-circuited") == n_threads
            assert mock_call.call_count == 3
            assert mock_get.call_count == 1
            assert mock_reconnect.call_count == 2
