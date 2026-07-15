"""Audit log repository.

Isolated from the former god-object ``database.models``. Imports the shared
``get_db`` lazily from ``database.models`` to avoid an import cycle (models
re-exports these repositories at import time).
"""
from __future__ import annotations


def _logs_where_clauses(filters):
    """Build SQL WHERE clauses and params for log filtering.

    Supported filter keys (all optional):
      - router: exact router_name match
      - admin_id: exact admin_id match
      - action: exact action match
      - since: timestamp string (UTC format) lower bound
    """
    filters = filters or {}
    clauses = []
    params = []
    router = filters.get("router")
    if router:
        clauses.append("router_name = ?")
        params.append(router)
    admin_id = filters.get("admin_id")
    if admin_id is not None:
        clauses.append("admin_id = ?")
        params.append(admin_id)
    action = filters.get("action")
    if action:
        clauses.append("action = ?")
        params.append(action)
    since = filters.get("since")
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    return clauses, params


def log_action(action: str, username: str, router_name: str, admin_id: int) -> None:
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (action, username, router_name, admin_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                action,
                username,
                router_name,
                admin_id,
                _now_utc(),
            ),
        )


def get_logs(limit=20, offset=0, filters=None):
    from database.models import get_db

    clauses, params = _logs_where_clauses(filters)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.extend([limit, offset])
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT action, username, router_name, timestamp FROM logs{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def get_logs_count(filters=None):
    from database.models import get_db

    clauses, params = _logs_where_clauses(filters)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM logs{where}", params)
        row = cursor.fetchone()
        return row[0] if row else 0


def get_distinct_log_actions():
    """Return the distinct action values recorded in the audit log."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT action FROM logs WHERE action IS NOT NULL AND action != '' ORDER BY action"
        )
        return [row["action"] for row in cursor.fetchall()]


def get_distinct_log_admins():
    """Return distinct (admin_id, username) pairs recorded in the audit log."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT admin_id, username FROM logs WHERE admin_id IS NOT NULL ORDER BY admin_id"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_distinct_log_routers():
    """Return the distinct router names recorded in the audit log."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT router_name FROM logs WHERE router_name IS NOT NULL AND router_name != '' ORDER BY router_name"
        )
        return [row["router_name"] for row in cursor.fetchall()]


def cleanup_old_logs(days: int) -> int:
    """Delete audit logs older than the requested retention period.

    The function is intentionally opt-in; init_db() never deletes production logs.
    """
    from datetime import datetime, timezone

    from database.models import UTC_TIMESTAMP_FORMAT, get_db

    if days <= 0:
        raise ValueError("days must be a positive integer")
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
    cutoff_text = datetime.fromtimestamp(cutoff, tz=timezone.utc).strftime(UTC_TIMESTAMP_FORMAT)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_text,))
        return cursor.rowcount


def _now_utc():
    from datetime import datetime, timezone

    from database.models import UTC_TIMESTAMP_FORMAT

    return datetime.now(timezone.utc).strftime(UTC_TIMESTAMP_FORMAT)
