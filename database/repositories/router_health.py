"""Repository for router health log — persistent watchdog state across restarts."""
import logging
from database.models import get_db, _now_utc

logger = logging.getLogger(__name__)


def record_health(router_key: str, status: str, error_msg: str = "") -> None:
    """حفظ نتيجة فحص صحة راوتر في قاعدة البيانات.

    status: 'online' أو 'offline'
    """
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO router_health_log (router_key, status, checked_at, error_msg)
                   VALUES (?, ?, ?, ?)""",
                (router_key, status, _now_utc(), error_msg or ""),
            )
    except Exception as e:
        logger.warning(f"Failed to record health for {router_key}: {e}")


def get_latest_health(router_key: str) -> dict | None:
    """استرداد آخر نتيجة فحص للراوتر. يُعيد None إن لم تُوجد سجلات."""
    try:
        with get_db() as conn:
            row = conn.execute(
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log
                   WHERE router_key = ?
                   ORDER BY checked_at DESC
                   LIMIT 1""",
                (router_key,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Failed to get latest health for {router_key}: {e}")
        return None


def get_all_latest_health() -> dict[str, dict]:
    """استرداد آخر نتيجة فحص لكل الراوترات.

    يُعيد dict مفاتيحه router_key وقيمه dicts من أعمدة الجدول.
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log AS h1
                   WHERE checked_at = (
                       SELECT MAX(checked_at) FROM router_health_log AS h2
                       WHERE h2.router_key = h1.router_key
                   )"""
            ).fetchall()
            return {row["router_key"]: dict(row) for row in rows}
    except Exception as e:
        logger.warning(f"Failed to get all latest health: {e}")
        return {}


def get_health_history(router_key: str, limit: int = 10) -> list[dict]:
    """استرداد آخر N نتيجة فحص لراوتر معين (مرتبة من الأحدث للأقدم)."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT router_key, status, checked_at, error_msg
                   FROM router_health_log
                   WHERE router_key = ?
                   ORDER BY checked_at DESC
                   LIMIT ?""",
                (router_key, limit),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"Failed to get health history for {router_key}: {e}")
        return []
