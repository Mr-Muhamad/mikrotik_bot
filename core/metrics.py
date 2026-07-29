"""Prometheus metrics exporter for MikroTik Bot.

Provides a simple HTTP endpoint that exposes metrics in Prometheus format.
Metrics include:
- bot_uptime: Seconds since bot started
- bot_messages_total: Total messages processed (by type)
- bot_mikrotik_requests_total: Total MikroTik API requests (by router)
- bot_mikrotik_request_duration_seconds: Request latency histogram
- bot_connection_pool_active: Active connections in pool
- bot_connection_pool_stale: Stale connections in pool
- bot_error_count_total: Error count by category and component
- bot_mikrotik_api_duration_seconds: MikroTik API duration histogram
- bot_backup_duration_seconds: Backup duration histogram
"""

import logging
import time
from collections import defaultdict

from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

# Bot start time for uptime calculation
_bot_start_time: float = time.time()

# Counters
_messages_total: dict[str, int] = defaultdict(int)
_mikrotik_requests_total: dict[str, int] = defaultdict(int)
_error_count_total: dict[str, dict[str, int]] = defaultdict(
    lambda: defaultdict(int)
)

# Latency tracking (simple list for now, can be improved with histogram buckets)
_request_latencies: list[float] = []
_mikrotik_api_latencies: list[float] = []
_backup_latencies: list[float] = []


def record_message_type(message_type: str) -> None:
    """Record a message of given type."""
    _messages_total[message_type] += 1


def record_mikrotik_request(router_key: str, duration_seconds: float) -> None:
    """Record a MikroTik API request with its duration."""
    _mikrotik_requests_total[router_key] += 1
    _request_latencies.append(duration_seconds)
    _mikrotik_api_latencies.append(duration_seconds)
    # Keep only last 1000 latencies to avoid memory bloat
    if len(_request_latencies) > 1000:
        _request_latencies.pop(0)
    if len(_mikrotik_api_latencies) > 1000:
        _mikrotik_api_latencies.pop(0)


def record_error(error_category: str, component: str) -> None:
    """Record an error occurrence by category and component."""
    _error_count_total[component][error_category] += 1


def record_backup_duration(backup_type: str, duration_seconds: float) -> None:
    """Record a backup operation duration."""
    _backup_latencies.append((backup_type, duration_seconds))
    if len(_backup_latencies) > 1000:
        _backup_latencies.pop(0)


def record_request_latency(handler_name: str, duration_seconds: float) -> None:
    """Record a handler request latency."""
    _request_latencies.append(duration_seconds)
    if len(_request_latencies) > 1000:
        _request_latencies.pop(0)


def get_uptime() -> float:
    """Get bot uptime in seconds."""
    return time.time() - _bot_start_time


def get_metrics_text(pool_metrics: RouterOSRow | None = None) -> str:  # noqa: C901
    """Generate Prometheus metrics in text format."""
    if pool_metrics is None:
        pool_metrics = {}
    lines = [
        "# HELP bot_uptime Bot uptime in seconds",
        "# TYPE bot_uptime gauge",
        f"bot_uptime {get_uptime():.1f}",
        "",
        "# HELP bot_messages_total Total messages processed by type",
        "# TYPE bot_messages_total counter",
    ]

    for msg_type, count in sorted(_messages_total.items()):
        lines.append(f'bot_messages_total{{type="{msg_type}"}} {count}')

    lines.extend(
        [
            "",
            "# HELP bot_mikrotik_requests_total Total MikroTik API requests by router",
            "# TYPE bot_mikrotik_requests_total counter",
        ]
    )

    for router, count in sorted(_mikrotik_requests_total.items()):
        lines.append(f'bot_mikrotik_requests_total{{router="{router}"}} {count}')

    # Latency percentiles (simple calculation)
    if _request_latencies:
        sorted_latencies = sorted(_request_latencies)
        n = len(sorted_latencies)
        p50 = sorted_latencies[int(n * 0.50)]
        p90 = sorted_latencies[int(n * 0.90)]
        p99 = sorted_latencies[min(int(n * 0.99), n - 1)]

        lines.extend(
            [
                "",
                "# HELP bot_mikrotik_request_duration_seconds MikroTik request latency",
                "# TYPE bot_mikrotik_request_duration_seconds summary",
                f'bot_mikrotik_request_duration_seconds{{quantile="0.5"}} {p50:.4f}',
                f'bot_mikrotik_request_duration_seconds{{quantile="0.9"}} {p90:.4f}',
                f'bot_mikrotik_request_duration_seconds{{quantile="0.99"}} {p99:.4f}',
                f"bot_mikrotik_request_duration_seconds_sum {sum(sorted_latencies):.4f}",
                f"bot_mikrotik_request_duration_seconds_count {n}",
            ]
        )

    # MikroTik API latency percentiles
    if _mikrotik_api_latencies:
        sorted_api_latencies = sorted(_mikrotik_api_latencies)
        n = len(sorted_api_latencies)
        p50 = sorted_api_latencies[int(n * 0.50)]
        p90 = sorted_api_latencies[int(n * 0.90)]
        p99 = sorted_api_latencies[min(int(n * 0.99), n - 1)]

        lines.extend(
            [
                "",
                "# HELP bot_mikrotik_api_duration_seconds MikroTik API latency",
                "# TYPE bot_mikrotik_api_duration_seconds summary",
                f'bot_mikrotik_api_duration_seconds{{quantile="0.5"}} {p50:.4f}',
                f'bot_mikrotik_api_duration_seconds{{quantile="0.9"}} {p90:.4f}',
                f'bot_mikrotik_api_duration_seconds{{quantile="0.99"}} {p99:.4f}',
                f"bot_mikrotik_api_duration_seconds_sum {sum(sorted_api_latencies):.4f}",
                f"bot_mikrotik_api_duration_seconds_count {n}",
            ]
        )

    # Backup duration percentiles
    if _backup_latencies:
        backup_durations = [d for _, d in _backup_latencies]
        if backup_durations:
            sorted_backup = sorted(backup_durations)
            n = len(sorted_backup)
            p50 = sorted_backup[int(n * 0.50)]
            p90 = sorted_backup[int(n * 0.90)]
            p99 = sorted_backup[min(int(n * 0.99), n - 1)]

            lines.extend(
                [
                    "",
                    "# HELP bot_backup_duration_seconds Backup operation latency",
                    "# TYPE bot_backup_duration_seconds summary",
                    f'bot_backup_duration_seconds{{quantile="0.5"}} {p50:.4f}',
                    f'bot_backup_duration_seconds{{quantile="0.9"}} {p90:.4f}',
                    f'bot_backup_duration_seconds{{quantile="0.99"}} {p99:.4f}',
                    f"bot_backup_duration_seconds_sum {sum(sorted_backup):.4f}",
                    f"bot_backup_duration_seconds_count {n}",
                ]
            )

    # Error count by component and category
    lines.extend(
        [
            "",
            "# HELP bot_error_count_total Total error count by component and category",
            "# TYPE bot_error_count_total counter",
        ]
    )
    for component in sorted(_error_count_total.keys()):
        for category, count in sorted(_error_count_total[component].items()):
            lines.append(
                f'bot_error_count_total{{component="{component}",category="{category}"}} {count}'
            )

    # Connection pool metrics
    if pool_metrics:
        lines.extend(
            [
                "",
                "# HELP bot_connection_pool_active Active connections in pool",
                "# TYPE bot_connection_pool_active gauge",
                f"bot_connection_pool_active {pool_metrics.get('active_connections', 0)}",
                "",
                "# HELP bot_connection_pool_stale Stale connections detected",
                "# TYPE bot_connection_pool_stale counter",
                f"bot_connection_pool_stale {pool_metrics.get('stale_connections', 0)}",
                "",
                "# HELP bot_connection_pool_successful Total successful connections",
                "# TYPE bot_connection_pool_successful counter",
                f"bot_connection_pool_successful {pool_metrics.get('successful', 0)}",
                "",
                "# HELP bot_connection_pool_failed Total failed connections",
                "# TYPE bot_connection_pool_failed counter",
                f"bot_connection_pool_failed {pool_metrics.get('failed', 0)}",
            ]
        )

    return "\n".join(lines) + "\n"
