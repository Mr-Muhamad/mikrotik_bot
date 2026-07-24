"""Repository for daily stats snapshots — تاريخ إحصائيات الروترات."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from database.models import get_db

logger = logging.getLogger(__name__)


def save_snapshot(router_key: str, data: dict[str, Any]) -> None:
    """حفظ snapshot يومي لإحصائيات راوتر.

    data: dict يحتوي على active_users, total_users, bytes_in, bytes_out (اختياري)
    يُستبدل السجل إن كان يوجد snapshot لنفس اليوم والراوتر (UPSERT).
    """

    today = date.today().isoformat()
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO stats_snapshots
                       (router_key, snapshot_date, active_users, total_users, bytes_in, bytes_out)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(router_key, snapshot_date) DO UPDATE SET
                       active_users = excluded.active_users,
                       total_users  = excluded.total_users,
                       bytes_in     = excluded.bytes_in,
                       bytes_out    = excluded.bytes_out""",
                (
                    router_key,
                    today,
                    data.get("active_users", 0),
                    data.get("total_users", 0),
                    data.get("bytes_in", 0),
                    data.get("bytes_out", 0),
                ),
            )
    except Exception as e:
        logger.warning(f"Failed to save snapshot for {router_key}: {e}")


def get_yesterday_snapshot(router_key: str) -> dict[str, Any] | None:
    """استرداد snapshot أمس للراوتر المحدد. يُعيد None إن لم يوجد."""

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        with get_db() as conn:
            row = conn.execute(
                """SELECT router_key, snapshot_date, active_users, total_users, bytes_in, bytes_out
                   FROM stats_snapshots
                   WHERE router_key = ? AND snapshot_date = ?""",
                (router_key, yesterday),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Failed to get yesterday snapshot for {router_key}: {e}")
        return None


def get_week_snapshots(router_key: str) -> list[dict[str, Any]]:
    """استرداد snapshots آخر 7 أيام للراوتر، مرتبة من الأقدم للأحدث."""

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT router_key, snapshot_date, active_users, total_users, bytes_in, bytes_out
                   FROM stats_snapshots
                   WHERE router_key = ? AND snapshot_date >= ?
                   ORDER BY snapshot_date ASC""",
                (router_key, week_ago),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"Failed to get week snapshots for {router_key}: {e}")
        return []
