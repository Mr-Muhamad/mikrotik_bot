"""Timed database execution helpers.

Provides ``timed_execute`` — a drop-in replacement for ``cursor.execute()``
that records per-query duration and feeds it into the metrics system so every
repository function automatically produces ``bot_db_queries_total`` and
``bot_db_query_duration_seconds`` metrics.

Usage in repository functions::

    from database.execute import timed_execute

    with get_db() as conn:
        cursor = conn.cursor()
        timed_execute(cursor, "SELECT ...", params, "read", "routers")
        row = cursor.fetchone()
        timed_execute(cursor, "INSERT INTO ...", params, "write", "routers")
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Sequence

from core.metrics import record_db_query

logger = logging.getLogger(__name__)


def timed_execute(
    cursor: sqlite3.Cursor,
    sql: str,
    params: Sequence[object] | None = None,
    operation: str = "query",
    table: str = "unknown",
) -> None:
    """Execute a cursor query with timing and metrics recording.

    Args:
        cursor: SQLite cursor or any DB-API cursor.
        sql: SQL statement to execute.
        params: Parameters for parameterised queries.
        operation: Logical operation name (``read``, ``write``, ``delete``, …).
        table: Target table name.
    """
    t0 = time.monotonic()
    try:
        cursor.execute(sql, params or ())
        elapsed_ms = (time.monotonic() - t0) * 1000
        record_db_query(operation, table, True, elapsed_ms)
    except Exception:  # noqa: BLE001 - catch-all: log all DB query failures before re-raising
        elapsed_ms = (time.monotonic() - t0) * 1000
        record_db_query(operation, table, False, elapsed_ms)
        raise
