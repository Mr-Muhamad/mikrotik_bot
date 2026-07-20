"""Backup schedule/results repository.

Manages ``backup_settings`` and ``backup_jobs`` rows. Isolated from the former
god-object ``database.models``.
"""

from __future__ import annotations

from datetime import UTC, datetime

# عدد سجلات النسخ المحتفظ بها لكل راوتر قبل الحذف التلقائي (retention).
BACKUP_JOBS_RETENTION_PER_ROUTER = 50


def _utc_now():
    from database.models import UTC_TIMESTAMP_FORMAT

    return datetime.now(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def get_backup_schedule() -> dict:
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT schedule_enabled, schedule_hour, schedule_minute FROM backup_settings WHERE id = 1"  # noqa: E501
        )
        row = cursor.fetchone()
        if row:
            return {
                "schedule_enabled": bool(row["schedule_enabled"]),
                "schedule_hour": int(row["schedule_hour"] or 3),
                "schedule_minute": int(row["schedule_minute"] or 0),
            }
    return {"schedule_enabled": False, "schedule_hour": 3, "schedule_minute": 0}


def save_backup_schedule(enabled: bool, hour: int = 3, minute: int = 0) -> None:
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE backup_settings SET
               schedule_enabled = ?,
               schedule_hour = ?,
               schedule_minute = ?
               WHERE id = 1""",
            (1 if enabled else 0, hour, minute),
        )


def record_backup_result(
    router_key: str,
    backup_type: str,
    success: bool,
    details: str,
    router_name: str = "",
    file_name: str = "",
) -> int:
    """Persist the result of a single backup run and return its row id.

    Records are pruned per router_key beyond BACKUP_JOBS_RETENTION_PER_ROUTER
    so the table stays bounded without an external cleanup job.
    """
    from database.models import get_db

    created_at = _utc_now()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO backup_jobs
               (router_key, router_name, backup_type, status, details, file_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                router_key,
                router_name,
                backup_type,
                "success" if success else "failed",
                details,
                file_name,
                created_at,
            ),
        )
        job_id = cursor.lastrowid
        _prune_backup_jobs(cursor, router_key)
    return job_id if job_id is not None else 0


def _prune_backup_jobs(cursor, router_key: str) -> None:
    cursor.execute("SELECT COUNT(*) FROM backup_jobs WHERE router_key = ?", (router_key,))
    count = cursor.fetchone()[0]
    if count > BACKUP_JOBS_RETENTION_PER_ROUTER:
        cursor.execute(
            """DELETE FROM backup_jobs WHERE router_key = ? AND id NOT IN (
                SELECT id FROM backup_jobs WHERE router_key = ?
                ORDER BY created_at DESC LIMIT ?
            )""",
            (router_key, router_key, BACKUP_JOBS_RETENTION_PER_ROUTER),
        )


def get_last_backup(router_key: str) -> dict | None:
    """Return the most recent backup record for a router, or None."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, router_key, router_name, backup_type, status, details,
                      file_name, created_at
               FROM backup_jobs WHERE router_key = ?
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            (router_key,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_recent_backups(limit: int = 20) -> list[dict]:
    """Return the most recent backup records across all routers."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, router_key, router_name, backup_type, status, details,
                      file_name, created_at
               FROM backup_jobs ORDER BY created_at DESC, id DESC LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
