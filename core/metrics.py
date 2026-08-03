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
from collections import defaultdict, deque
from collections.abc import Sequence

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

# Latency tracking — bounded deques (O(1) eviction, no O(n) pop(0) trims)
_request_latencies: deque[float] = deque(maxlen=1000)
_mikrotik_api_latencies: deque[float] = deque(maxlen=1000)
_backup_latencies: deque[tuple[str, float]] = deque(maxlen=1000)

# Action success/fail counters per router+command
_action_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Action durations per router+command (for average tracking)
_action_durations: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))

# Database query counters per operation+table
_db_query_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Database query durations per operation+table
_db_query_durations: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))

# Telegram API counters per handler/method
_telegram_requests_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Telegram API durations per handler/method
_telegram_request_durations: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))

# Component-level total operations (success/fail per component)
_component_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Error timestamps per component for sliding-window rate calculation
_ERROR_TIMESTAMPS_WINDOW = 200
_error_timestamps_per_component: dict[str, deque[float]] = defaultdict(
    lambda: deque(maxlen=_ERROR_TIMESTAMPS_WINDOW)
)

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


def record_request_latency(handler_name: str, duration_seconds: float) -> None:
    """Record a handler request latency."""
    _request_latencies.append(duration_seconds)


def record_action(router_key: str, command: str, success: bool, duration_ms: float) -> None:
    """Record an action outcome with timing for a specific router and command."""
    key = f"{router_key}:{command}"
    if success:
        _action_total[key]["success"] += 1
    else:
        _action_total[key]["fail"] += 1
    _action_durations[key].append(duration_ms)


def record_db_query(operation: str, table: str, success: bool, duration_ms: float) -> None:
    """Record a database query with timing for a specific operation and table."""
    key = f"{operation}:{table}"
    if success:
        _db_query_total[key]["success"] += 1
    else:
        _db_query_total[key]["fail"] += 1
    _db_query_durations[key].append(duration_ms)


def record_telegram_request(handler: str, success: bool, duration_ms: float) -> None:
    """Record a Telegram handler/method call with timing."""
    if success:
        _telegram_requests_total[handler]["success"] += 1
    else:
        _telegram_requests_total[handler]["fail"] += 1
    _telegram_request_durations[handler].append(duration_ms)


def get_uptime() -> float:
    """Get bot uptime in seconds."""
    return time.time() - _bot_start_time


def _append_block_header(lines: list[str], metric_name: str, help_text: str, metric_type: str) -> None:
    """Append a blank line plus a Prometheus HELP/TYPE pair for a metric."""
    lines.extend(
        ["", f"# HELP {metric_name} {help_text}", f"# TYPE {metric_name} {metric_type}"]
    )


def _append_summary_values(
    lines: list[str],
    metric_name: str,
    durations: Sequence[float],
    label_body: str = "",
) -> None:
    """Append p50/p90/p99/sum/count value lines for a duration series.

    ``label_body`` holds static labels without braces or trailing comma
    (e.g. ``router="r",command="c"``); when empty the summary is rendered
    without static labels.
    """
    if not durations:
        return
    sorted_d = sorted(durations)
    n = len(sorted_d)
    p50 = sorted_d[int(n * 0.50)]
    p90 = sorted_d[int(n * 0.90)]
    p99 = sorted_d[min(int(n * 0.99), n - 1)]
    label_prefix = f"{{{label_body}," if label_body else ""
    label_suffix = "}" if label_body else ""
    sum_labels = f"{{{label_body}}}" if label_body else ""
    lines.append(f'{metric_name}{{{label_prefix}quantile="0.5"{label_suffix}}} {p50:.4f}')
    lines.append(f'{metric_name}{{{label_prefix}quantile="0.9"{label_suffix}}} {p90:.4f}')
    lines.append(f'{metric_name}{{{label_prefix}quantile="0.99"{label_suffix}}} {p99:.4f}')
    lines.append(f"{metric_name}_sum{sum_labels} {sum(sorted_d):.4f}")
    lines.append(f"{metric_name}_count{sum_labels} {n}")


def _append_uptime_and_messages(lines: list[str]) -> None:
    lines.extend(
        [
            "# HELP bot_uptime Bot uptime in seconds",
            "# TYPE bot_uptime gauge",
            f"bot_uptime {get_uptime():.1f}",
            "",
            "# HELP bot_messages_total Total messages processed by type",
            "# TYPE bot_messages_total counter",
        ]
    )
    for msg_type, count in sorted(_messages_total.items()):
        lines.append(f'bot_messages_total{{type="{msg_type}"}} {count}')


def _append_mikrotik_requests(lines: list[str]) -> None:
    _append_block_header(
        lines, "bot_mikrotik_requests_total", "Total MikroTik API requests by router", "counter"
    )
    for router, count in sorted(_mikrotik_requests_total.items()):
        lines.append(f'bot_mikrotik_requests_total{{router="{router}"}} {count}')


def _append_request_latency(lines: list[str]) -> None:
    if not _request_latencies:
        return
    _append_block_header(
        lines, "bot_mikrotik_request_duration_seconds", "MikroTik request latency", "summary"
    )
    _append_summary_values(lines, "bot_mikrotik_request_duration_seconds", _request_latencies)


def _append_api_latency(lines: list[str]) -> None:
    if not _mikrotik_api_latencies:
        return
    _append_block_header(
        lines, "bot_mikrotik_api_duration_seconds", "MikroTik API latency", "summary"
    )
    _append_summary_values(lines, "bot_mikrotik_api_duration_seconds", _mikrotik_api_latencies)


def _append_backup_latency(lines: list[str]) -> None:
    if not _backup_latencies:
        return
    backup_durations = [d for _, d in _backup_latencies]
    _append_block_header(lines, "bot_backup_duration_seconds", "Backup operation latency", "summary")
    _append_summary_values(lines, "bot_backup_duration_seconds", backup_durations)


def _append_errors(lines: list[str]) -> None:
    _append_block_header(
        lines, "bot_error_count_total", "Total error count by component and category", "counter"
    )
    for component in sorted(_error_count_total):
        for category, count in sorted(_error_count_total[component].items()):
            lines.append(
                f'bot_error_count_total{{component="{component}",category="{category}"}} {count}'
            )


def _append_actions(lines: list[str]) -> None:
    if not _action_total:
        return
    _append_block_header(
        lines, "bot_action_total", "Total actions by router, command, and status", "counter"
    )
    for key in sorted(_action_total):
        router, command = key.split(":", 1)
        for status in ("success", "fail"):
            count = _action_total[key][status]
            if count:
                lines.append(
                    f'bot_action_total{{router="{router}",command="{command}",status="{status}"}} {count}'
                )
    if _action_durations:
        _append_block_header(
            lines, "bot_action_duration_seconds", "Action duration by router and command", "summary"
        )
        for key in sorted(_action_durations):
            router, command = key.split(":", 1)
            _append_summary_values(
                lines,
                "bot_action_duration_seconds",
                _action_durations[key],
                label_body=f'router="{router}",command="{command}"',
            )


def _append_db_queries(lines: list[str]) -> None:
    if not _db_query_total:
        return
    _append_block_header(
        lines, "bot_db_queries_total", "Total database queries by operation and table", "counter"
    )
    for key in sorted(_db_query_total):
        operation, table = key.split(":", 1)
        for status in ("success", "fail"):
            count = _db_query_total[key][status]
            if count:
                lines.append(
                    f'bot_db_queries_total{{operation="{operation}",table="{table}",status="{status}"}} {count}'
                )
    if _db_query_durations:
        _append_block_header(
            lines,
            "bot_db_query_duration_seconds",
            "Database query duration by operation and table",
            "summary",
        )
        for key in sorted(_db_query_durations):
            operation, table = key.split(":", 1)
            _append_summary_values(
                lines,
                "bot_db_query_duration_seconds",
                _db_query_durations[key],
                label_body=f'operation="{operation}",table="{table}"',
            )


def _append_telegram_requests(lines: list[str]) -> None:
    if not _telegram_requests_total:
        return
    _append_block_header(
        lines,
        "bot_telegram_requests_total",
        "Total Telegram handler invocations by handler and status",
        "counter",
    )
    for handler in sorted(_telegram_requests_total):
        for status in ("success", "fail"):
            count = _telegram_requests_total[handler][status]
            if count:
                lines.append(
                    f'bot_telegram_requests_total{{handler="{handler}",status="{status}"}} {count}'
                )
    if _telegram_request_durations:
        _append_block_header(
            lines,
            "bot_telegram_handler_duration_seconds",
            "Telegram handler duration by handler",
            "summary",
        )
        for handler in sorted(_telegram_request_durations):
            _append_summary_values(
                lines,
                "bot_telegram_handler_duration_seconds",
                _telegram_request_durations[handler],
                label_body=f'handler="{handler}"',
            )


def _append_health(lines: list[str]) -> None:
    _append_block_header(
        lines,
        "bot_health_status",
        "Overall bot health (0=healthy, 1=degraded, 2=critical)",
        "gauge",
    )
    lines.append(f"bot_health_status {get_health_status()}")


def _append_error_rate(lines: list[str]) -> None:
    if not _component_total:
        return
    _append_block_header(lines, "bot_error_rate", "Error rate (failures / total) per component", "gauge")
    for component in sorted(_component_total):
        lines.append(f'bot_error_rate{{component="{component}"}} {get_error_rate(component):.4f}')


def _append_pool_metrics(lines: list[str], pool_metrics: RouterOSRow) -> None:
    if not pool_metrics:
        return
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


def get_metrics_text(pool_metrics: RouterOSRow | None = None) -> str:
    """Generate Prometheus metrics in text format."""
    if pool_metrics is None:
        pool_metrics = {}
    lines: list[str] = []
    _append_uptime_and_messages(lines)
    _append_mikrotik_requests(lines)
    _append_request_latency(lines)
    _append_api_latency(lines)
    _append_backup_latency(lines)
    _append_errors(lines)
    _append_actions(lines)
    _append_db_queries(lines)
    _append_telegram_requests(lines)
    _append_health(lines)
    _append_error_rate(lines)
    _append_pool_metrics(lines, pool_metrics)
    return "\n".join(lines) + "\n"
