"""Deterministic tests for the per-router write lock in :class:`MikrotikAPI`.

Write commands targeting the same router are serialized while read-only commands
run in parallel and writes to different routers proceed independently. All
external I/O is mocked (connection pool + command execution + throttle) so the
behaviour is reproducible on every run with no timing-dependent sleeps.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from core.mikrotik_api import (
    MikrotikAPI,
    _is_write_command,  # type: ignore[reportPrivateUsage]
)
from core.mikrotik_client import RouterOSRow


def _run_concurrent(api: MikrotikAPI, jobs: list[tuple[str, str]]) -> int:
    """Fires one worker per job, each calling ``_execute_with_retry``.

    Returns the maximum number of ``_call_command`` invocations observed in
    flight at once, measured from inside the mocked command call.
    """
    n_threads = len(jobs)
    barrier = threading.Barrier(n_threads)
    counter: dict[str, int] = {"active": 0, "max": 0}
    counter_lock = threading.Lock()
    fake_connection = MagicMock()

    def tracked_call(conn: object, cmd: str, **kwargs: object) -> list[RouterOSRow]:
        del conn, cmd, kwargs
        with counter_lock:
            counter["active"] += 1
            counter["max"] = max(counter["max"], counter["active"])
        time.sleep(0.02)
        with counter_lock:
            counter["active"] -= 1
        return []

    def worker(job: tuple[str, str]) -> None:
        router_key, command = job
        barrier.wait(timeout=15)
        api._execute_with_retry(router_key, command, 30)  # type: ignore[reportPrivateUsage]

    with (
        patch.object(api._pool, "get_connection", return_value=fake_connection),  # type: ignore[reportPrivateUsage]
        patch.object(api._pool, "reconnect", return_value=fake_connection),  # type: ignore[reportPrivateUsage]
        patch.object(api, "_call_command", side_effect=tracked_call),
        patch.object(api, "_throttle"),
    ):
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(worker, job) for job in jobs]
            for future in futures:
                future.result(timeout=15)

    return counter["max"]


class TestWriteLockSerialization:
    def test_concurrent_writes_same_router_are_serialized(self) -> None:
        api = MikrotikAPI()
        jobs = [("r1", "ip/hotspot/user/add") for _ in range(8)]
        max_concurrent = _run_concurrent(api, jobs)
        assert max_concurrent == 1

    def test_concurrent_reads_run_in_parallel(self) -> None:
        api = MikrotikAPI()
        jobs = [("r1", "ip/hotspot/user/print") for _ in range(8)]
        max_concurrent = _run_concurrent(api, jobs)
        assert max_concurrent > 1

    def test_writes_on_different_routers_run_in_parallel(self) -> None:
        api = MikrotikAPI()
        jobs = [("r1", "ip/hotspot/user/add"), ("r2", "ip/hotspot/user/add")]
        max_concurrent = _run_concurrent(api, jobs)
        assert max_concurrent == 2

    def test_non_blocking_write_takes_the_same_lock(self) -> None:
        api = MikrotikAPI()
        barrier = threading.Barrier(2)
        counter: dict[str, int] = {"active": 0, "max": 0}
        counter_lock = threading.Lock()
        fake_connection = MagicMock()

        def tracked_call(conn: object, cmd: str, **kwargs: object) -> list[RouterOSRow]:
            del conn, cmd, kwargs
            with counter_lock:
                counter["active"] += 1
                counter["max"] = max(counter["max"], counter["active"])
            time.sleep(0.02)
            with counter_lock:
                counter["active"] -= 1
            return []

        def block_worker() -> None:
            barrier.wait(timeout=15)
            api._execute_with_retry("r1", "ip/hotspot/user/add", 30)  # type: ignore[reportPrivateUsage]

        def non_blocking_worker() -> None:
            barrier.wait(timeout=15)
            api.execute_non_blocking("r1", "ip/hotspot/user/add", name="x")

        with (
            patch.object(api._pool, "get_connection", return_value=fake_connection),  # type: ignore[reportPrivateUsage]
            patch.object(api._pool, "reconnect", return_value=fake_connection),  # type: ignore[reportPrivateUsage]
            patch.object(api, "_call_command", side_effect=tracked_call),
            patch.object(api, "_throttle"),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(block_worker),
                    executor.submit(non_blocking_worker),
                ]
                for future in futures:
                    future.result(timeout=15)

        assert counter["max"] == 1


@pytest.mark.parametrize(
    ("command", "is_write"),
    [
        ("ip/hotspot/user/print", False),
        ("ip/hotspot/user/get", False),
        ("system/resource/print", False),
        ("print", False),
        ("ip/hotspot/user/add", True),
        ("ip/hotspot/user/set", True),
        ("ip/hotspot/user/remove", True),
        ("system/reboot", True),
        ("ip/hotspot/user/reset-counters", True),
        ("ip/hotspot/user/create-and-activate-profile", True),
        ("tool/fetch", True),
        ("import", True),
        ("mystery/verb", True),
    ],
)
def test_write_command_classifier(command: str, is_write: bool) -> None:
    assert _is_write_command(command) is is_write
