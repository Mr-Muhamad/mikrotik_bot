import asyncio
import logging
import os
import random
import sys
import time
from unittest.mock import patch

import psutil

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.hotspot_manager import HotspotManager
from tests.mocks.mikrotik_api_mock import MikrotikAPIMock
from utils.formatters import format_hotspot_user


async def monitor_resources(duration: int, process: psutil.Process):
    """Monitors CPU and RAM usage in the background."""
    print(f"--- Starting Resource Monitor for {duration} seconds ---")
    cpu_measurements = []
    mem_measurements = []

    start_time = time.time()
    while time.time() - start_time < duration:
        cpu = process.cpu_percent(interval=0.5)
        mem = process.memory_info().rss / (1024 * 1024)  # MB
        cpu_measurements.append(cpu)
        mem_measurements.append(mem)
        print(f"[Resource Monitor] CPU: {cpu}% | RAM: {mem:.2f} MB")

    avg_cpu = sum(cpu_measurements) / len(cpu_measurements) if cpu_measurements else 0
    avg_mem = sum(mem_measurements) / len(mem_measurements) if mem_measurements else 0
    print(f"--- Monitor Finished. Avg CPU: {avg_cpu:.2f}%, Avg RAM: {avg_mem:.2f} MB ---")
    return avg_cpu, avg_mem


async def simulate_load(hotspot_manager, router_key: str, num_requests: int):
    """Simulates high concurrent load on the HotspotManager."""
    print(f"--- Simulating {num_requests} concurrent requests ---")
    start_time = time.time()

    async def worker(worker_id):
        op_type = random.choice(["list", "search", "add", "format", "stats"])
        try:
            if op_type == "list":
                hotspot_manager.list_users(router_key, limit=50)
            elif op_type == "search":
                hotspot_manager.search_users(router_key, f"test_{worker_id}")
            elif op_type == "add":
                hotspot_manager.add_user(router_key, f"user_{worker_id}", "pass", "default")
            elif op_type == "format":
                user = hotspot_manager.get_user(router_key, "*1")
                if user:
                    format_hotspot_user(user)
            elif op_type == "stats":
                hotspot_manager.get_hotspot_stats(router_key)
        except Exception:
            logger.debug("Stress test worker error on op %s", op_type)

    tasks = [asyncio.create_task(worker(i)) for i in range(num_requests)]
    await asyncio.gather(*tasks)

    duration = time.time() - start_time
    print(
        f"--- Simulated {num_requests} requests in {duration:.2f} seconds ({num_requests / duration:.2f} req/s) ---"  # noqa: E501
    )


async def main():
    # Setup mock environment
    mock_api = MikrotikAPIMock()
    process = psutil.Process(os.getpid())
    process.cpu_percent()  # initial call

    with (
        patch("core.mikrotik_api.mikrotik_api", mock_api),
        patch("core.hotspot_manager.mikrotik_api", mock_api),
    ):
        hm = HotspotManager()

        print("\n[Test 1] Light Load (100 concurrent requests)")
        monitor_task = asyncio.create_task(monitor_resources(3, process))
        await simulate_load(hm, "discovered_1", 100)
        await monitor_task

        print("\n[Test 2] Heavy Load (1000 concurrent requests)")
        monitor_task = asyncio.create_task(monitor_resources(5, process))
        await simulate_load(hm, "discovered_1", 1000)
        await monitor_task

        print("\n[Test 3] Cache Performance (2000 concurrent reads)")

        async def read_worker(i):
            try:
                hm.list_users("discovered_1", limit=100)
                hm.get_hotspot_stats("discovered_1")
            except Exception:
                logger.debug("Read worker %d error", i)

        monitor_task = asyncio.create_task(monitor_resources(5, process))
        start_time = time.time()
        tasks = [asyncio.create_task(read_worker(i)) for i in range(2000)]
        await asyncio.gather(*tasks)
        dur = time.time() - start_time
        print(f"--- Read Load: 2000 requests in {dur:.2f}s ({2000 / dur:.2f} req/s) ---")
        await monitor_task


if __name__ == "__main__":
    asyncio.run(main())
