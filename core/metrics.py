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
_backup_latencies: list[tuple[str, float]] = []

# Action success/fail counters per router+command
_action_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Action durations per router+command (for average tracking)
_action_durations: dict[str, list[float]] = defaultdict(list)

# Database query counters per operation+table
_db_query_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Database query durations per operation+table
_db_query_durations: dict[str, list[float]] = defaultdict(list)

# Telegram API counters per handler/method
_telegram_requests_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Telegram API durations per handler/method
_telegram_request_durations: dict[str, list[float]] = defaultdict(list)

# Component-level total operations (success/fail per component)
_component_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Error timestamps per component for sliding-window rate calculation
_ERROR_TIMESTAMPS_WINDOW = 200
_error_timestamps_per_component: dict[str, list[float]] = defaultdict(list)

# Health thresholds
_ERROR_RATE_WARN = 0.10  # 10% error rate triggers degraded
_ERROR_RATE_CRIT = 0.25  # 25% error rate triggers critical


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


def record_component_result(component: str, success: bool) -> None:
    """Record a component operation result for error-rate calculation.

    Tracks total operations (success/fail) per component and maintains a
    sliding window of error timestamps for threshold-based health checks.
    """
    if success:
        _component_total[component]["success"] += 1
    else:
        _component_total[component]["fail"] += 1
        ts = _error_timestamps_per_component[component]
        ts.append(time.time())
        # Trim sliding window
        if len(ts) > _ERROR_TIMESTAMPS_WINDOW:
            ts.pop(0)


def get_error_rate(component: str) -> float:
    """Calculate error rate for a component over the recent sliding window.

    Returns fraction of failed operations vs total operations (0.0 to 1.0).
    Returns 0.0 if no operations recorded for this component.
    """
    totals = _component_total.get(component)
    if not totals:
        return 0.0
    total = totals["success"] + totals["fail"]
    if total == 0:
        return 0.0
    return totals["fail"] / total


def get_health_status() -> int:
    """Determine overall bot health based on component error rates.

    Returns:
        0 = healthy
        1 = degraded (any component exceeds WARN threshold)
        2 = critical (any component exceeds CRIT threshold)
    """
    degraded = False
    for component in list(_component_total):
        rate = get_error_rate(component)
        if rate >= _ERROR_RATE_CRIT:
            return 2
        if rate >= _ERROR_RATE_WARN:
            degraded = True
    return 1 if degraded else 0


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


def record_action(router_key: str, command: str, success: bool, duration_ms: float) -> None:
    """Record an action outcome with timing for a specific router and command."""
    key = f"{router_key}:{command}"
    if success:
        _action_total[key]["success"] += 1
    else:
        _action_total[key]["fail"] += 1
    _action_durations[key].append(duration_ms)
    if len(_action_durations[key]) > 1000:
        _action_durations[key].pop(0)


def record_db_query(operation: str, table: str, success: bool, duration_ms: float) -> None:
    """Record a database query with timing for a specific operation and table."""
    key = f"{operation}:{table}"
    if success:
        _db_query_total[key]["success"] += 1
    else:
        _db_query_total[key]["fail"] += 1
    _db_query_durations[key].append(duration_ms)
    if len(_db_query_durations[key]) > 1000:
        _db_query_durations[key].pop(0)


def record_telegram_request(handler: str, success: bool, duration_ms: float) -> None:
    """Record a Telegram handler/method call with timing."""
    if success:
        _telegram_requests_total[handler]["success"] += 1
    else:
        _telegram_requests_total[handler]["fail"] += 1
    _telegram_request_durations[handler].append(duration_ms)
    if len(_telegram_request_durations[handler]) > 1000:
        _telegram_request_durations[handler].pop(0)


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

    # Action counters per router+command
    if _action_total:
        lines.extend(
            [
                "",
                "# HELP bot_action_total Total actions by router, command, and status",
                "# TYPE bot_action_total counter",
            ]
        )
        for key in sorted(_action_total):
            router, command = key.split(":", 1)
            for status in ("success", "fail"):
                count = _action_total[key][status]
                if count:
                    lines.append(
                        f'bot_action_total{{router="{router}",command="{command}",status="{status}"}} {count}'
                    )
        # Action duration summary
        if _action_durations:
            lines.extend(
                [
                    "",
                    "# HELP bot_action_duration_seconds Action duration by router and command",
                    "# TYPE bot_action_duration_seconds summary",
                ]
            )
            for key in sorted(_action_durations):
                router, command = key.split(":", 1)
                durations = _action_durations[key]
                if durations:
                    sorted_d = sorted(durations)
                    n = len(sorted_d)
                    p50 = sorted_d[int(n * 0.50)]
                    p90 = sorted_d[int(n * 0.90)]
                    p99 = sorted_d[min(int(n * 0.99), n - 1)]
                    lines.append(
                        f'bot_action_duration_seconds{{router="{router}",command="{command}",quantile="0.5"}} {p50:.4f}'
                    )
                    lines.append(
                        f'bot_action_duration_seconds{{router="{router}",command="{command}",quantile="0.9"}} {p90:.4f}'
                    )
                    lines.append(
                        f'bot_action_duration_seconds{{router="{router}",command="{command}",quantile="0.99"}} {p99:.4f}'
                    )
                    lines.append(
                        f'bot_action_duration_seconds_sum{{router="{router}",command="{command}"}} {sum(sorted_d):.4f}'
                    )
                    lines.append(
                        f'bot_action_duration_seconds_count{{router="{router}",command="{command}"}} {n}'
                    )

    # Database query counters per operation+table
    if _db_query_total:
        lines.extend(
            [
                "",
                "# HELP bot_db_queries_total Total database queries by operation and table",
                "# TYPE bot_db_queries_total counter",
            ]
        )
        for key in sorted(_db_query_total):
            operation, table = key.split(":", 1)
            for status in ("success", "fail"):
                count = _db_query_total[key][status]
                if count:
                    lines.append(
                        f'bot_db_queries_total{{operation="{operation}",table="{table}",status="{status}"}} {count}'
                    )
        # DB query duration percentiles
        if _db_query_durations:
            lines.extend(
                [
                    "",
                    "# HELP bot_db_query_duration_seconds Database query duration by operation and table",
                    "# TYPE bot_db_query_duration_seconds summary",
                ]
            )
            for key in sorted(_db_query_durations):
                operation, table = key.split(":", 1)
                durations = _db_query_durations[key]
                if durations:
                    sorted_d = sorted(durations)
                    n = len(sorted_d)
                    p50 = sorted_d[int(n * 0.50)]
                    p90 = sorted_d[int(n * 0.90)]
                    p99 = sorted_d[min(int(n * 0.99), n - 1)]
                    lines.append(
                        f'bot_db_query_duration_seconds{{operation="{operation}",table="{table}",quantile="0.5"}} {p50:.4f}'
                    )
                    lines.append(
                        f'bot_db_query_duration_seconds{{operation="{operation}",table="{table}",quantile="0.9"}} {p90:.4f}'
                    )
                    lines.append(
                        f'bot_db_query_duration_seconds{{operation="{operation}",table="{table}",quantile="0.99"}} {p99:.4f}'
                    )
                    lines.append(
                        f'bot_db_query_duration_seconds_sum{{operation="{operation}",table="{table}"}} {sum(sorted_d):.4f}'
                    )
                    lines.append(
                        f'bot_db_query_duration_seconds_count{{operation="{operation}",table="{table}"}} {n}'
                    )

    # Telegram request counters per handler
    if _telegram_requests_total:
        lines.extend(
            [
                "",
                "# HELP bot_telegram_requests_total Total Telegram handler invocations by handler and status",
                "# TYPE bot_telegram_requests_total counter",
            ]
        )
        for handler in sorted(_telegram_requests_total):
            for status in ("success", "fail"):
                count = _telegram_requests_total[handler][status]
                if count:
                    lines.append(
                        f'bot_telegram_requests_total{{handler="{handler}",status="{status}"}} {count}'
                    )
        # Telegram handler duration percentiles
        if _telegram_request_durations:
            lines.extend(
                [
                    "",
                    "# HELP bot_telegram_handler_duration_seconds Telegram handler duration by handler",
                    "# TYPE bot_telegram_handler_duration_seconds summary",
                ]
            )
            for handler in sorted(_telegram_request_durations):
                durations = _telegram_request_durations[handler]
                if durations:
                    sorted_d = sorted(durations)
                    n = len(sorted_d)
                    p50 = sorted_d[int(n * 0.50)]
                    p90 = sorted_d[int(n * 0.90)]
                    p99 = sorted_d[min(int(n * 0.99), n - 1)]
                    lines.append(
                        f'bot_telegram_handler_duration_seconds{{handler="{handler}",quantile="0.5"}} {p50:.4f}'
                    )
                    lines.append(
                        f'bot_telegram_handler_duration_seconds{{handler="{handler}",quantile="0.9"}} {p90:.4f}'
                    )
                    lines.append(
                        f'bot_telegram_handler_duration_seconds{{handler="{handler}",quantile="0.99"}} {p99:.4f}'
                    )
                    lines.append(
                        f'bot_telegram_handler_duration_seconds_sum{{handler="{handler}"}} {sum(sorted_d):.4f}'
                    )
                    lines.append(
                        f'bot_telegram_handler_duration_seconds_count{{handler="{handler}"}} {n}'
                    )

    # Health status gauge
    health_status = get_health_status()
    lines.extend(
        [
            "",
            "# HELP bot_health_status Overall bot health (0=healthy, 1=degraded, 2=critical)",
            "# TYPE bot_health_status gauge",
            f"bot_health_status {health_status}",
        ]
    )

    # Error rate per component
    if _component_total:
        lines.extend(
            [
                "",
                "# HELP bot_error_rate Error rate (failures / total) per component",
                "# TYPE bot_error_rate gauge",
            ]
        )
        for component in sorted(_component_total):
            rate = get_error_rate(component)
            lines.append(
                f'bot_error_rate{{component="{component}"}} {rate:.4f}'
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
