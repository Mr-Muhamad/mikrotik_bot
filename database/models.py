"""Database access layer — connection infrastructure and public re-exports.

The aggregate-specific CRUD logic (audit logs, admin roles, card batches,
user sessions, PDF settings, routers, backups) was extracted into cohesive
repository modules under ``database/repositories``. This module keeps the
shared connection infrastructure (DB_PATH, get_db, init_db, migrations) and
re-exports the repository functions so existing callers
(``from database.models import ...`` and ``patch("database.models.X")``) keep
working unchanged.

Longer term, callers should import directly from ``database.repositories.*``
and this re-export shim can be removed.
"""

import logging
import os
import re
import sqlite3
import warnings
from contextlib import contextmanager
from datetime import UTC, datetime

from config import ADMIN_IDS
from utils.crypto import decrypt_data, decrypt_password, encrypt_data, encrypt_password

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "mikrotik_bot.db")
logger = logging.getLogger(__name__)
UTC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

VALID_ROLES = ("admin", "operator", "viewer")


def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections with automatic commit/rollback."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now_utc() -> str:
    return datetime.now(UTC).strftime(UTC_TIMESTAMP_FORMAT)


# Public alias for use in other repository modules.
now_utc = _now_utc


_VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_table_name(table_name: str) -> None:
    if not _VALID_IDENTIFIER_RE.match(table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")


def _validate_column_name(column_name: str) -> None:
    if not _VALID_IDENTIFIER_RE.match(column_name):
        raise ValueError(f"Invalid column name: {column_name!r}")


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    _validate_table_name(table_name)
    _validate_column_name(column_name)
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cursor.fetchall())


def _add_column_if_missing(cursor: sqlite3.Cursor, table_name: str, column_def: str) -> None:
    _validate_table_name(table_name)
    column_name = column_def.split()[0]
    _validate_column_name(column_name)
    if _column_exists(cursor, table_name, column_name):
        return
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
    logger.info(f"Added {table_name} column: {column_def}")


def create_indexes() -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_logs_admin ON logs(admin_id)",
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)",
            (
                "CREATE INDEX IF NOT EXISTS idx_routers_active "
                "ON discovered_routers(is_active, added_at DESC)"
            ),
            "CREATE INDEX IF NOT EXISTS idx_routers_ip ON discovered_routers(ip_address)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_backup_jobs_router ON backup_jobs(router_key)",
            "CREATE INDEX IF NOT EXISTS idx_backup_jobs_created ON backup_jobs(created_at DESC)",
            (
                "CREATE INDEX IF NOT EXISTS idx_health_router_time "
                "ON router_health_log(router_key, checked_at DESC)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_snapshots_router_date "
                "ON stats_snapshots(router_key, snapshot_date DESC)"
            ),
            "CREATE INDEX IF NOT EXISTS idx_tracked_messages_chat ON tracked_messages(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_tracked_messages_date ON tracked_messages(tracked_at)",
        ]
        for idx in indexes:
            try:
                cursor.execute(idx)
            except Exception as e:
                logger.debug(f"Index creation skipped: {e}")


def migrate_passwords():
    """Deprecated: column is handled by Alembic initial migration."""
    warnings.warn("migrate_passwords() is deprecated", DeprecationWarning, stacklevel=1)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM discovered_routers WHERE password != ''")
        rows = cursor.fetchall()
        updated = 0
        for row in rows:
            plain = row["password"]
            if not plain:
                continue
            # توكنات Fernet تبدأ دائماً بـ "gAAAAA" — إذا بدأت بها فهي مشفّرة بالفعل
            if not plain.startswith("gAAAAA"):
                encrypted = encrypt_password(plain)
                cursor.execute(
                    "UPDATE discovered_routers SET password = ? WHERE id = ?",
                    (encrypted, row["id"]),
                )
                updated += 1
        if updated:
            logger.info(f"Migrated {updated} plaintext passwords to encrypted")


def migrate_add_name_alias():
    """Deprecated: columns are handled by Alembic initial migration."""
    warnings.warn("migrate_add_name_alias() is deprecated", DeprecationWarning, stacklevel=1)
    with get_db() as conn:
        cursor = conn.cursor()
        _add_column_if_missing(cursor, "discovered_routers", "name_alias TEXT DEFAULT ''")
        _add_column_if_missing(cursor, "discovered_routers", "owner_id INTEGER DEFAULT 0")
        _add_column_if_missing(
            cursor, "user_sessions", "last_activity DATETIME DEFAULT CURRENT_TIMESTAMP"
        )
        _add_column_if_missing(cursor, "user_sessions", "session_timeout INTEGER DEFAULT 600")


def migrate_backup_schedule_columns():
    """Deprecated: columns are handled by Alembic initial migration."""
    warnings.warn(
        "migrate_backup_schedule_columns() is deprecated",
        DeprecationWarning,
        stacklevel=1,
    )
    with get_db() as conn:
        cursor = conn.cursor()
        for col_def in (
            "schedule_enabled INTEGER DEFAULT 0",
            "schedule_hour INTEGER DEFAULT 3",
            "schedule_minute INTEGER DEFAULT 0",
        ):
            _add_column_if_missing(cursor, "backup_settings", col_def)


def migrate_pdf_settings_columns():
    """Deprecated: columns are handled by Alembic initial migration."""
    warnings.warn("migrate_pdf_settings_columns() is deprecated", DeprecationWarning, stacklevel=1)
    with get_db() as conn:
        cursor = conn.cursor()
        for col_def in (
            "brand_name TEXT DEFAULT ''",
            "hotspot_dns TEXT DEFAULT ''",
            "show_qr INTEGER DEFAULT 1",
            "cards_per_page INTEGER DEFAULT 40",
            "label_spacing_single REAL DEFAULT 1.0",
            "label_spacing_dual REAL DEFAULT 1.0",
            "value_max_font_single INTEGER DEFAULT 12",
            "value_max_font_dual INTEGER DEFAULT 11",
        ):
            _add_column_if_missing(cursor, "pdf_settings", col_def)


def migrate_card_batches_columns():
    """Deprecated: columns are handled by Alembic initial migration."""
    warnings.warn("migrate_card_batches_columns() is deprecated", DeprecationWarning, stacklevel=1)
    with get_db() as conn:
        cursor = conn.cursor()
        # Older databases created card_batches without created_by; add it idempotently.
        _add_column_if_missing(cursor, "card_batches", "created_by INTEGER")
        # نظام الفواتير: بيانات البيع والدفع
        _add_column_if_missing(cursor, "card_batches", "customer_name TEXT DEFAULT ''")
        _add_column_if_missing(cursor, "card_batches", "payment_status TEXT DEFAULT 'unpaid'")
        _add_column_if_missing(cursor, "card_batches", "sale_price REAL DEFAULT 0")
        _add_column_if_missing(cursor, "card_batches", "sold_at DATETIME")


def init_db():
    import os

    from alembic.config import Config

    from alembic import command  # type: ignore[reportAttributeAccessIssue]

    # Run alembic migrations
    alembic_cfg_path = os.path.join(PROJECT_ROOT, "alembic.ini")
    alembic_cfg = Config(alembic_cfg_path)
    # Set the script_location and sqlalchemy.url dynamically
    alembic_dir = os.path.join(PROJECT_ROOT, "alembic")
    alembic_cfg.set_main_option("script_location", alembic_dir)

    # In Windows, sqlite:///C:/path/to/db.sqlite requires formatting
    db_uri = f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_uri)

    # Temporarily set cwd to project root so alembic finds env.py
    old_cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        os.chdir(old_cwd)

    seed_admin_roles(ADMIN_IDS)
    # Column additions (passwords, name_alias, backup_schedule, pdf_settings,
    # card_batches) are fully handled by the Alembic initial migration.
    # The migrate_*() functions below are retained as deprecated idempotent
    # helpers for any database created before Alembic was introduced.


# ─── Re-export stats_snapshots functions ──────────────────────────────

# ─── Re-export operator_permissions functions ─────────────────────────

# ─── Re-exports from cohesive repository modules ──────────────────
from database.repositories.admin_roles import (
    ensure_admin_role,
    get_admin_role,
    list_admin_roles,
    seed_admin_roles,
    set_admin_role,
)
from database.repositories.audit_logs import (
    cleanup_old_logs,
    get_distinct_log_actions,
    get_distinct_log_admins,
    get_distinct_log_routers,
    get_logs,
    get_logs_count,
    log_action,
)
from database.repositories.backups import (
    BACKUP_JOBS_RETENTION_PER_ROUTER,
    get_backup_schedule,
    get_last_backup,
    get_recent_backups,
    record_backup_result,
    save_backup_schedule,
)
from database.repositories.card_batches import (
    delete_card_batch,
    get_card_batch,
    get_card_batches_count,
    get_sales_summary,
    list_card_batches,
    save_card_batch,
    update_batch_payment,
)
from database.repositories.chat_messages import (
    add_tracked_message,
    delete_stale_records,
    get_tracked_messages,
    remove_tracked_messages,
)
from database.repositories.operator_permissions import (
    get_operator_routers,
)
from database.repositories.pdf_settings import (
    PDF_ALLOWED_COLUMNS,
    get_pdf_settings,
    update_pdf_settings,
)
from database.repositories.router_health import (
    cleanup_health_history,
    get_all_latest_health,
    get_health_history,
    get_latest_health,
    record_health,
)
from database.repositories.routers import (
    delete_router,
    get_router_by_id,
    get_router_by_ip,
    get_router_display_name,
    get_saved_routers,
    save_discovered_router,
    update_router_alias,
    update_router_credentials,
    update_router_identity,
    update_router_last_seen,
)
from database.repositories.user_sessions import (
    get_user_session,
    save_user_session,
)

__all__ = [
    "DB_PATH",
    "UTC_TIMESTAMP_FORMAT",
    "VALID_ROLES",
    "get_db",
    "init_db",
    "encrypt_password",
    "decrypt_password",
    "encrypt_data",
    "decrypt_data",
    "log_action",
    "get_logs",
    "get_logs_count",
    "get_distinct_log_actions",
    "get_distinct_log_admins",
    "get_distinct_log_routers",
    "cleanup_old_logs",
    "ensure_admin_role",
    "seed_admin_roles",
    "get_admin_role",
    "set_admin_role",
    "list_admin_roles",
    "save_card_batch",
    "list_card_batches",
    "get_card_batches_count",
    "get_card_batch",
    "delete_card_batch",
    "get_sales_summary",
    "update_batch_payment",
    "get_user_session",
    "save_user_session",
    "get_pdf_settings",
    "update_pdf_settings",
    "PDF_ALLOWED_COLUMNS",
    "save_discovered_router",
    "get_saved_routers",
    "get_router_by_id",
    "get_router_by_ip",
    "update_router_credentials",
    "update_router_last_seen",
    "update_router_identity",
    "delete_router",
    "update_router_alias",
    "get_router_display_name",
    "get_backup_schedule",
    "save_backup_schedule",
    "record_backup_result",
    "get_last_backup",
    "get_recent_backups",
    "BACKUP_JOBS_RETENTION_PER_ROUTER",
    "add_tracked_message",
    "get_tracked_messages",
    "remove_tracked_messages",
    "delete_stale_records",
    "record_health",
    "get_latest_health",
    "get_all_latest_health",
    "get_health_history",
    "cleanup_health_history",
    "get_operator_routers",
]
