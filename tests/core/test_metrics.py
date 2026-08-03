"""Tests for core.metrics — Prometheus exporter."""

import core.metrics as m


class TestRecordMessageType:
    def setup_method(self):
        m._messages_total.clear()  # type: ignore[reportPrivateUsage]

    def test_increments_counter(self):
        m.record_message_type("text")
        m.record_message_type("text")
        assert m._messages_total["text"] == 2  # type: ignore[reportPrivateUsage]

    def test_different_types(self):
        m.record_message_type("text")
        m.record_message_type("photo")
        assert m._messages_total["text"] == 1  # type: ignore[reportPrivateUsage]
        assert m._messages_total["photo"] == 1  # type: ignore[reportPrivateUsage]


class TestRecordMikrotikRequest:
    def setup_method(self):
        m._mikrotik_requests_total.clear()  # type: ignore[reportPrivateUsage]
        m._request_latencies.clear()  # type: ignore[reportPrivateUsage]

    def test_increments_and_stores_latency(self):
        m.record_mikrotik_request("router1", 0.25)
        assert m._mikrotik_requests_total["router1"] == 1  # type: ignore[reportPrivateUsage]
        assert list(m._request_latencies) == [0.25]  # type: ignore[reportPrivateUsage]

    def test_evicts_old_latencies_at_1000(self):
        for i in range(1005):
            m.record_mikrotik_request("r", float(i))
        assert len(m._request_latencies) == 1000  # type: ignore[reportPrivateUsage]
        assert m._request_latencies[0] == 5.0  # type: ignore[reportPrivateUsage]


class TestBoundedLatencyStores:
    """Guards the O(1) sliding-window storage (no O(n) pop(0) trims)."""

    def setup_method(self):
        m._request_latencies.clear()  # type: ignore[reportPrivateUsage]
        m._mikrotik_api_latencies.clear()  # type: ignore[reportPrivateUsage]
        m._backup_latencies.clear()  # type: ignore[reportPrivateUsage]
        m._action_durations.clear()  # type: ignore[reportPrivateUsage]
        m._db_query_durations.clear()  # type: ignore[reportPrivateUsage]
        m._telegram_request_durations.clear()  # type: ignore[reportPrivateUsage]
        m._error_timestamps_per_component.clear()  # type: ignore[reportPrivateUsage]

    def test_request_latencies_is_bounded_deque(self):
        from collections import deque

        assert isinstance(m._request_latencies, deque)
        assert m._request_latencies.maxlen == 1000

    def test_api_latencies_is_bounded_deque(self):
        from collections import deque

        assert isinstance(m._mikrotik_api_latencies, deque)
        assert m._mikrotik_api_latencies.maxlen == 1000

    def test_backup_latencies_is_bounded_deque(self):
        from collections import deque

        assert isinstance(m._backup_latencies, deque)
        assert m._backup_latencies.maxlen == 1000

    def test_action_durations_is_bounded_deque(self):
        from collections import deque

        m.record_action("router1", "print", True, 5.0)
        assert isinstance(m._action_durations["router1:print"], deque)  # type: ignore[reportPrivateUsage]
        assert m._action_durations["router1:print"].maxlen == 1000  # type: ignore[reportPrivateUsage]

    def test_db_query_durations_is_bounded_deque(self):
        from collections import deque

        m.record_db_query("select", "logs", True, 3.0)
        assert isinstance(m._db_query_durations["select:logs"], deque)  # type: ignore[reportPrivateUsage]
        assert m._db_query_durations["select:logs"].maxlen == 1000  # type: ignore[reportPrivateUsage]

    def test_telegram_request_durations_is_bounded_deque(self):
        from collections import deque

        m.record_telegram_request("handler", True, 4.0)
        assert isinstance(m._telegram_request_durations["handler"], deque)  # type: ignore[reportPrivateUsage]
        assert m._telegram_request_durations["handler"].maxlen == 1000  # type: ignore[reportPrivateUsage]

    def test_error_timestamps_is_bounded_deque(self):
        from collections import deque

        m.record_component_result("ROUTER", False)
        assert isinstance(m._error_timestamps_per_component["ROUTER"], deque)  # type: ignore[reportPrivateUsage]
        assert m._error_timestamps_per_component["ROUTER"].maxlen == 200  # type: ignore[reportPrivateUsage]


class TestGetUptime:
    def test_returns_positive_float(self):
        assert m.get_uptime() >= 0


class TestGetMetricsText:
    def setup_method(self):
        m._messages_total.clear()  # type: ignore[reportPrivateUsage]
        m._mikrotik_requests_total.clear()  # type: ignore[reportPrivateUsage]
        m._request_latencies.clear()  # type: ignore[reportPrivateUsage]

    def test_empty_metrics(self):
        text = m.get_metrics_text()
        assert "bot_uptime" in text
        assert "bot_messages_total" in text

    def test_includes_message_counts(self):
        m.record_message_type("text")
        m.record_message_type("text")
        m.record_message_type("photo")
        text = m.get_metrics_text()
        assert 'bot_messages_total{type="photo"} 1' in text
        assert 'bot_messages_total{type="text"} 2' in text

    def test_includes_request_counts(self):
        m.record_mikrotik_request("router1", 0.1)
        text = m.get_metrics_text()
        assert 'bot_mikrotik_requests_total{router="router1"} 1' in text

    def test_includes_latency_percentiles(self):
        for i in range(100):
            m.record_mikrotik_request("r", float(i) / 100)
        text = m.get_metrics_text()
        assert 'quantile="0.5"' in text
        assert 'quantile="0.9"' in text
        assert 'quantile="0.99"' in text
        assert "bot_mikrotik_request_duration_seconds_sum" in text
        assert "bot_mikrotik_request_duration_seconds_count" in text

    def test_no_latency_section_when_empty(self):
        text = m.get_metrics_text()
        assert "request_duration" not in text

    def test_pool_metrics(self):
        pool = {
            "active_connections": 3,
            "stale_connections": 1,
            "successful": 10,
            "failed": 2,
        }
        text = m.get_metrics_text(pool_metrics=pool)  # type: ignore[reportArgumentType]
        assert "bot_connection_pool_active 3" in text
        assert "bot_connection_pool_stale 1" in text
        assert "bot_connection_pool_successful 10" in text
        assert "bot_connection_pool_failed 2" in text

    def test_pool_metrics_none(self):
        text = m.get_metrics_text(pool_metrics=None)
        assert "connection_pool" not in text
