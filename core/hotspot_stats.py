"""Hotspot statistics and usage-report builders.

Extracted from ``core.hotspot_manager`` to keep that module focused on
user/host lifecycle operations. These functions are pure with respect to
the MikroTik API client: they take an API handle and return plain dicts,
so the presentation/aggregation responsibility lives here instead of in
the user-management class.
"""

import logging
import re

from librouteros.exceptions import LibRouterosError

from utils.formatters import format_bytes, parse_bytes

logger = logging.getLogger(__name__)

_GB = 1_000_000_000

_DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})|(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
_DAY_SLASH_RE = re.compile(r"(\d{1,2})[/](\d{1,2})")


def parse_reset_day(comment: str) -> int | None:
    """Extract the reset day (1-31) from a hotspot user comment.

    Supports:
    - YYYY-MM-DD or YYYY/MM/DD -> group(3)
    - DD-MM-YYYY or DD/MM/YYYY -> group(4)
    - DD/MM or MM/DD -> group(1) or group(2)
    - Legacy /DD
    - Plain day number (1-31) inside comment
    """
    comment = str(comment or "").strip()
    if not comment:
        return None

    match = _DATE_RE.search(comment)
    if match:
        try:
            if match.group(3):
                val = int(match.group(3))
                if 1 <= val <= 31:
                    return val
            if match.group(4):
                val = int(match.group(4))
                if 1 <= val <= 31:
                    return val
        except (ValueError, TypeError):
            pass

    match_slash = _DAY_SLASH_RE.search(comment)
    if match_slash:
        try:
            val1 = int(match_slash.group(1))
            val2 = int(match_slash.group(2))
            if 1 <= val1 <= 31:
                return val1
            elif 1 <= val2 <= 31:
                return val2
        except (ValueError, TypeError):
            pass

    if "/" in comment:
        try:
            val = int(comment.split("/")[-1])
            if 1 <= val <= 31:
                return val
        except (ValueError, TypeError):
            pass

    # Try extracting standalone day number 1-31
    digits = re.findall(r"\b([1-9]|[12]\d|3[01])\b", comment)
    if digits:
        try:
            return int(digits[0])
        except (ValueError, TypeError):
            pass

    return None



def get_hotspot_stats(api, router_key: str, day: int | None = None) -> dict | None:
    """Return hotspot statistics, optionally filtered to a single reset day.

    When ``day`` is ``None`` the ``reset_list`` is empty and ``reset_days``
    exposes every day that has reset records so the UI can offer a picker.
    When ``day`` is provided, ``reset_list`` contains only that day's resets.
    """
    try:
        users = api.execute_long(
            router_key,
            "ip/hotspot/user/print",
            **{".proplist": ".id,name,limit-bytes-total,comment,disabled"},
        )

        active_count = 0
        inactive_count = 0
        categories = {
            "10 GB": 0,
            "20 GB": 0,
            "30 GB": 0,
            "40 GB": 0,
            "50 GB": 0,
            "أخرى": 0,
        }
        resets_by_day: dict[int, list[tuple[str, str, str]]] = {}

        for user in users:
            is_disabled = str(user.get("disabled", "false")).lower() == "true"

            if is_disabled:
                inactive_count += 1
            else:
                active_count += 1

                limit_raw = user.get("limit-bytes-total", "")
                if limit_raw and str(limit_raw) != "0":
                    try:
                        limit_str = str(limit_raw)
                        limit_bytes = (
                            int(parse_bytes(limit_str))
                            if not limit_str.isdigit()
                            else int(limit_str)
                        )
                        limit_gb = limit_bytes / _GB
                        if 10 <= limit_gb < 20:
                            categories["10 GB"] += 1
                        elif 20 <= limit_gb < 30:
                            categories["20 GB"] += 1
                        elif 30 <= limit_gb < 40:
                            categories["30 GB"] += 1
                        elif 40 <= limit_gb < 50:
                            categories["50 GB"] += 1
                        elif limit_gb >= 50:
                            categories["50 GB"] += 1
                        else:
                            categories["أخرى"] += 1
                    except (ValueError, TypeError):
                        categories["أخرى"] += 1
                else:
                    categories["أخرى"] += 1

            reset_day = parse_reset_day(user.get("comment", ""))
            if reset_day is not None:
                limit = format_bytes(user.get("limit-bytes-total", ""))
                uname = str(user.get("name", "—"))
                comment = str(user.get("comment", "") or uname)
                resets_by_day.setdefault(reset_day, []).append((uname, comment, limit))

        reset_days = sorted(resets_by_day.keys(), reverse=True)
        if day is None:
            reset_list: list[tuple[str, str, str]] = []
            selected_day = None
        else:
            reset_list = resets_by_day.get(day, [])
            selected_day = day

        return {
            "total": len(users),
            "active": active_count,
            "inactive": inactive_count,
            "categories": categories,
            "resets_by_day": resets_by_day,
            "reset_days": reset_days,
            "reset_list": reset_list,
            "selected_day": selected_day,
        }
    except (LibRouterosError, ConnectionError, OSError) as e:
        logger.error(f"Error getting hotspot stats: {e}")
        return None


def build_usage_report(api, router_key: str, top_n: int = 15) -> dict:
    """Build an exportable Hotspot usage report for a router.

    Fetches all hotspot users (long-running call) and classifies them into
    summary statistics, top consumers, expired, near-limit and inactive groups.
    Returns a plain dict with a flat ``rows`` list suitable for CSV export.
    """
    users = api.execute_long(
        router_key,
        "ip/hotspot/user/print",
        **{".proplist": ".id,name,profile,disabled,bytes-in,bytes-out,limit-bytes-total,comment"},
    )

    rows: list[dict] = []
    total_bytes_all = 0
    active_count = 0
    disabled_count = 0
    with_limit_count = 0

    for u in users:
        if not isinstance(u, dict):
            continue
        name = u.get("name", "")
        profile = u.get("profile", "")
        is_disabled = str(u.get("disabled", "false")).lower() == "true"
        if is_disabled:
            disabled_count += 1
        else:
            active_count += 1

        try:
            bytes_in = int(u.get("bytes-in", 0) or 0)
        except (ValueError, TypeError):
            bytes_in = 0
        try:
            bytes_out = int(u.get("bytes-out", 0) or 0)
        except (ValueError, TypeError):
            bytes_out = 0

        total_bytes = bytes_in + bytes_out
        total_bytes_all += total_bytes

        limit_raw = u.get("limit-bytes-total", "")
        limit = 0
        if limit_raw and str(limit_raw) not in ("0", "0.0", ""):
            try:
                limit = int(limit_raw)
            except (ValueError, TypeError):
                limit = 0
        if limit > 0:
            with_limit_count += 1

        percent = (total_bytes / limit * 100) if limit > 0 else 0.0
        comment = u.get("comment", "")

        rows.append(
            {
                "name": name,
                "profile": profile,
                "status": "disabled" if is_disabled else "active",
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
                "total_bytes": total_bytes,
                "total_str": format_bytes(str(total_bytes)),
                "limit": limit,
                "limit_str": format_bytes(str(limit)) if limit else "—",
                "percent": percent,
                "comment": comment,
            }
        )

    top_consumers = sorted(rows, key=lambda r: r["total_bytes"], reverse=True)[:top_n]
    expired = [r for r in rows if r["limit"] > 0 and r["total_bytes"] >= r["limit"]]
    near_limit = [r for r in rows if r["limit"] > 0 and 90 <= r["percent"] < 100]
    inactive = [r for r in rows if r["status"] == "disabled"]

    return {
        "router_key": router_key,
        "total": len(rows),
        "active": active_count,
        "disabled": disabled_count,
        "with_limit": with_limit_count,
        "total_bytes": total_bytes_all,
        "total_bytes_str": format_bytes(str(total_bytes_all)),
        "top_consumers": top_consumers,
        "expired": expired,
        "near_limit": near_limit,
        "inactive": inactive,
        "rows": rows,
    }
