"""Tests for core.chart_generator module."""

from core.chart_generator import generate_sales_chart, generate_trend_chart


def test_generate_trend_chart_with_data():
    snapshots = [
        {
            "snapshot_date": "2026-07-20",
            "active_users": 15,
            "total_users": 50,
            "bytes_in": 1000,
            "bytes_out": 2000,
        },
        {
            "snapshot_date": "2026-07-21",
            "active_users": 20,
            "total_users": 52,
            "bytes_in": 1500,
            "bytes_out": 2500,
        },
    ]
    img_bytes = generate_trend_chart(snapshots, title="اختبار النشاط")
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0
    # Check PNG magic bytes header (\x89PNG)
    assert img_bytes.startswith(b"\x89PNG")


def test_generate_trend_chart_empty():
    img_bytes = generate_trend_chart([])
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0
    assert img_bytes.startswith(b"\x89PNG")


def test_generate_sales_chart_with_data():
    batches = [
        {"profile": "1 GB", "count": 10},
        {"profile": "5 GB", "count": 5},
        {"profile": "1 GB", "count": 12},
    ]
    img_bytes = generate_sales_chart(batches, title="اختبار المبيعات")
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0
    assert img_bytes.startswith(b"\x89PNG")


def test_generate_sales_chart_empty():
    img_bytes = generate_sales_chart([])
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0
    assert img_bytes.startswith(b"\x89PNG")
