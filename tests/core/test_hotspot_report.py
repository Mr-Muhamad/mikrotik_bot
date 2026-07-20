"""Tests for Hotspot usage report building and CSV export."""

from unittest.mock import patch

from bot.handlers.hotspot_report import build_csv
from core.hotspot_manager import hotspot_manager


def _fake_users():
    return [
        {
            "name": "userA",
            "profile": "10GB",
            "disabled": "false",
            "bytes-in": "900000000",
            "bytes-out": "100000000",
            "limit-bytes-total": "10000000000",
            "comment": "vip",
        },
        {
            "name": "userB",
            "profile": "20GB",
            "disabled": "false",
            "bytes-in": "21000000000",
            "bytes-out": "500000000",
            "limit-bytes-total": "20000000000",
            "comment": "",
        },
        {
            "name": "userC",
            "profile": "5GB",
            "disabled": "true",
            "bytes-in": "100",
            "bytes-out": "100",
            "limit-bytes-total": "0",
            "comment": "",
        },
        {
            "name": "userD",
            "profile": "10GB",
            "disabled": "false",
            "bytes-in": "9000000000",
            "bytes-out": "900000000",
            "limit-bytes-total": "10000000000",
            "comment": "",
        },
    ]


def test_build_usage_report_classifies_users():
    fake = _fake_users()
    with patch("core.hotspot_manager.mikrotik_api.execute_long", return_value=fake):
        report = hotspot_manager.build_usage_report("discovered_1")

    assert report["total"] == 4
    assert report["active"] == 3
    assert report["disabled"] == 1
    assert report["with_limit"] == 3

    names = [r["name"] for r in report["rows"]]
    assert set(names) == {"userA", "userB", "userC", "userD"}

    top = [r["name"] for r in report["top_consumers"]]
    assert top[0] == "userB"

    expired_names = {r["name"] for r in report["expired"]}
    assert "userB" in expired_names

    near_names = {r["name"] for r in report["near_limit"]}
    assert "userD" in near_names
    assert "userA" not in near_names

    inactive_names = {r["name"] for r in report["inactive"]}
    assert inactive_names == {"userC"}


def test_build_csv_header_and_rows():
    fake = _fake_users()
    with patch("core.hotspot_manager.mikrotik_api.execute_long", return_value=fake):
        report = hotspot_manager.build_usage_report("discovered_1")

    csv_text = build_csv(report)
    lines = csv_text.splitlines()
    assert (
        lines[0]
        == "name,profile,status,bytes_in,bytes_out,total_bytes,total_str,limit_str,percent,comment"
    )
    assert len(lines) == 1 + len(report["rows"])
    assert any("userA" in line for line in lines[1:])
