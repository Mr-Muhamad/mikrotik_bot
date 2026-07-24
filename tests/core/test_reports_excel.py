"""Tests for core.reports_excel module."""

import io

import openpyxl

from core.reports_excel import build_sales_excel_report, build_usage_excel_report


def test_build_usage_excel_report():
    report = {
        "router_key": "discovered_1",
        "rows": [
            {
                "name": "user1",
                "profile": "1 GB",
                "status": "نشط",
                "bytes_in": 1024,
                "bytes_out": 2048,
                "total_bytes": 3072,
                "limit_str": "5 GB",
                "percent": 61.4,
                "comment": "VIP",
            }
        ],
    }
    excel_bytes = build_usage_excel_report(report, title="تقرير اختبار")
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # Verify openpyxl can load the generated workbook
    buf = io.BytesIO(excel_bytes)
    wb = openpyxl.load_workbook(buf)
    sheet = wb.active
    assert sheet is not None
    assert sheet.title == "تقرير الاستخدام"
    assert sheet["A3"].value == "اسم المستخدم"
    assert sheet["A4"].value == "user1"


def test_build_sales_excel_report():
    batches = [
        {
            "id": 1,
            "name": "batch1",
            "profile": "10 GB",
            "batch_type": "hotspot",
            "count": 50,
            "created_at": "2026-07-24 12:00",
        }
    ]
    excel_bytes = build_sales_excel_report(batches, title="مبيعات اختبار")
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    buf = io.BytesIO(excel_bytes)
    wb = openpyxl.load_workbook(buf)
    sheet = wb.active
    assert sheet is not None
    assert sheet.title == "المبيعات"
    assert sheet["A3"].value == "المعرف (ID)"
    assert sheet["B4"].value == "batch1"
