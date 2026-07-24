"""Tests for core.metrics — Prometheus exporter."""

import core.metrics as m


class TestRecordMessageType:
    def setup_method(self):
        m._messages_total.clear()

    def test_increments_counter(self):
        m.record_message_type("text")
        m.record_message_type("text")
        assert m._messages_total["text"] == 2

    def test_different_types(self):
        m.record_message_type("text")
        m.record_message_type("photo")
        assert m._messages_total["text"] == 1
        assert m._messages_total["photo"] == 1


class TestRecordMikrotikRequest:
    def setup_method(self):
        m._mikrotik_requests_total.clear()
        m._request_latencies.clear()

    def test_increments_and_stores_latency(self):
        m.record_mikrotik_request("router1", 0.25)
        assert m._mikrotik_requests_total["router1"] == 1
        assert m._request_latencies == [0.25]

    def test_evicts_old_latencies_at_1000(self):
        for i in range(1005):
            m.record_mikrotik_request("r", float(i))
        assert len(m._request_latencies) == 1000
        assert m._request_latencies[0] == 5.0


class TestGetUptime:
    def test_returns_positive_float(self):
        assert m.get_uptime() >= 0


class TestGetMetricsText:
    def setup_method(self):
        m._messages_total.clear()
        m._mikrotik_requests_total.clear()
        m._request_latencies.clear()

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
        text = m.get_metrics_text(pool_metrics=pool)
        assert "bot_connection_pool_active 3" in text
        assert "bot_connection_pool_stale 1" in text
        assert "bot_connection_pool_successful 10" in text
        assert "bot_connection_pool_failed 2" in text

    def test_pool_metrics_none(self):
        text = m.get_metrics_text(pool_metrics=None)
        assert "connection_pool" not in text
