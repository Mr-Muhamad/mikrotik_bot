"""Repository for router health log — persistent watchdog state across restarts."""

import logging
from datetime import UTC

from core.mikrotik_client import RouterOSRow
from database.execute import timed_execute
from database.models import get_db, now_utc

logger = logging.getLogger(__name__)


def record_health(router_key: str, status: str, error_msg: str = "") -> None:
    """حفظ نتيجة فحص صحة راوتر في قاعدة البيانات.

    status: 'online' أو 'offline'
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            timed_execute(
                cursor,
                """INSERT INTO router_health_log (router_key, status, checked_at, error_msg)
                   VALUES (?, ?, ?, ?)""",
                (router_key, status, now_utc(), error_msg or ""),
                "write",
                "router_health_log",
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to record health for %s (error type: %s): %s",
            router_key, type(e).__name__, e,
        )


def get_latest_health(router_key: str) -> RouterOSRow | None:
    """استرداد آخر نتيجة فحص للراوتر. يُعيد None إن لم تُوجد سجلات."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            timed_execute(
                cursor,
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log
                   WHERE router_key = ?
                   ORDER BY checked_at DESC
                   LIMIT 1""",
                (router_key,),
                "read",
                "router_health_log",
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to get latest health for %s (error type: %s): %s",
            router_key, type(e).__name__, e,
        )
        return None


def get_all_latest_health() -> dict[str, RouterOSRow]:
    """استرداد آخر نتيجة فحص لكل الراوترات.

    يُعيد dict مفاتيحه router_key وقيمه dicts من أعمدة الجدول.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            timed_execute(
                cursor,
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log AS h1
                   WHERE checked_at = (
                       SELECT MAX(checked_at) FROM router_health_log AS h2
                       WHERE h2.router_key = h1.router_key
                   )""",
                None,
                "read",
                "router_health_log",
            )
            rows = cursor.fetchall()
            return {row["router_key"]: dict(row) for row in rows}
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to get all latest health (error type: %s): %s",
            type(e).__name__, e,
        )
        return {}


def get_health_history(router_key: str, limit: int = 10) -> list[RouterOSRow]:
    """استرداد آخر N نتيجة فحص لراوتر معين (مرتبة من الأحدث للأقدم)."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            timed_execute(
                cursor,
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log
                   WHERE router_key = ?
                   ORDER BY checked_at DESC
                   LIMIT ?""",
                (router_key, limit),
                "read",
                "router_health_log",
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to get health history for %s (error type: %s): %s",
            router_key, type(e).__name__, e,
        )
        return []


def cleanup_health_history(days: int = 7) -> int:
    """مسح سجلات فحص الصحة الأقدم من العدد المحدد من الأيام.
    يُعيد عدد السجلات التي تم مسحها.
    """
    from datetime import datetime, timedelta

    from database.models import UTC_TIMESTAMP_FORMAT

    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_text = cutoff.strftime(UTC_TIMESTAMP_FORMAT)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            timed_execute(
                cursor, "DELETE FROM router_health_log WHERE checked_at < ?",
                (cutoff_text,), "write", "router_health_log",
            )
            return cursor.rowcount
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to cleanup health history (error type: %s): %s",
            type(e).__name__, e,
        )
        return 0
