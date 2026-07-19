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
import sqlite3
import os
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from config import DEFAULT_API_PORT, ADMIN_IDS
from utils.crypto import encrypt_password, decrypt_password, encrypt_data, decrypt_data

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mikrotik_bot.db")
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


def _now_utc():
    return datetime.now(timezone.utc).strftime(UTC_TIMESTAMP_FORMAT)


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cursor.fetchall())


def _add_column_if_missing(cursor, table_name: str, column_def: str) -> None:
    column_name = column_def.split()[0]
    if _column_exists(cursor, table_name, column_name):
        return
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
    logger.info(f"Added {table_name} column: {column_def}")


def _create_indexes():
    with get_db() as conn:
        cursor = conn.cursor()
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_logs_admin ON logs(admin_id)",
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_routers_active ON discovered_routers(is_active, added_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_routers_ip ON discovered_routers(ip_address)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_backup_jobs_router ON backup_jobs(router_key)",
            "CREATE INDEX IF NOT EXISTS idx_backup_jobs_created ON backup_jobs(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_health_router_time ON router_health_log(router_key, checked_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_router_date ON stats_snapshots(router_key, snapshot_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_tracked_messages_chat ON tracked_messages(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_tracked_messages_date ON tracked_messages(tracked_at)",
        ]
        for idx in indexes:
            try:
                cursor.execute(idx)
            except Exception as e:
                logger.debug(f"Index creation skipped: {e}")


def migrate_passwords():
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
                cursor.execute("UPDATE discovered_routers SET password = ? WHERE id = ?", (encrypted, row["id"]))
                updated += 1
        if updated:
            logger.info(f"Migrated {updated} plaintext passwords to encrypted")


def migrate_add_name_alias():
    with get_db() as conn:
        cursor = conn.cursor()
        _add_column_if_missing(cursor, "discovered_routers", "name_alias TEXT DEFAULT ''")


def migrate_backup_schedule_columns():
    with get_db() as conn:
        cursor = conn.cursor()
        for col_def in (
            "schedule_enabled INTEGER DEFAULT 0",
            "schedule_hour INTEGER DEFAULT 3",
            "schedule_minute INTEGER DEFAULT 0",
        ):
            _add_column_if_missing(cursor, "backup_settings", col_def)


def migrate_pdf_settings_columns():
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
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                username TEXT,
                router_name TEXT,
                admin_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_roles (
                admin_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                changed_by INTEGER,
                changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS card_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                router_key TEXT NOT NULL,
                name TEXT NOT NULL,
                batch_type TEXT NOT NULL,
                profile TEXT DEFAULT '',
                comment_prefix TEXT DEFAULT '',
                count INTEGER DEFAULT 0,
                cards_json TEXT NOT NULL,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                margin_top REAL DEFAULT 10,
                margin_bottom REAL DEFAULT 10,
                margin_left REAL DEFAULT 10,
                margin_right REAL DEFAULT 10,
                border_width REAL DEFAULT 1,
                card_width REAL DEFAULT 85,
                card_height REAL DEFAULT 55,
                spacing_x REAL DEFAULT 5,
                spacing_y REAL DEFAULT 5,
                cards_per_row INTEGER DEFAULT 4,
                header_text TEXT DEFAULT '',
                footer_text TEXT DEFAULT '',
                brand_name TEXT DEFAULT '',
                hotspot_dns TEXT DEFAULT '',
                show_qr INTEGER DEFAULT 1,
                cards_per_page INTEGER DEFAULT 40,
                label_spacing_single REAL DEFAULT 1.0,
                label_spacing_dual REAL DEFAULT 1.0,
                value_max_font_single INTEGER DEFAULT 12,
                value_max_font_dual INTEGER DEFAULT 11
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_dir TEXT DEFAULT './backups',
                send_telegram INTEGER DEFAULT 1,
                save_local INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                router_key TEXT,
                router_name TEXT DEFAULT '',
                backup_type TEXT DEFAULT 'full',
                status TEXT DEFAULT 'success',
                details TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS router_health_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                router_key TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                error_msg TEXT DEFAULT ''
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                tracked_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                router_key TEXT NOT NULL,
                snapshot_date DATE NOT NULL,
                active_users INTEGER DEFAULT 0,
                total_users INTEGER DEFAULT 0,
                bytes_in INTEGER DEFAULT 0,
                bytes_out INTEGER DEFAULT 0,
                UNIQUE(router_key, snapshot_date)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_router_permissions (
                operator_id INTEGER NOT NULL,
                router_id INTEGER NOT NULL,
                assigned_by INTEGER,
                assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (operator_id, router_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                selected_router TEXT DEFAULT 'router1',
                current_action TEXT,
                action_data TEXT
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS discovered_routers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL UNIQUE,
                mac_address TEXT,
                identity TEXT DEFAULT 'Unknown',
                version TEXT,
                board TEXT,
                software_id TEXT,
                platform TEXT DEFAULT 'MikroTik',
                uptime TEXT,
                port INTEGER DEFAULT {DEFAULT_API_PORT},
                username TEXT,
                password TEXT,
                last_seen DATETIME,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                name_alias TEXT DEFAULT ''
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM pdf_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO pdf_settings DEFAULT VALUES")

        cursor.execute("SELECT COUNT(*) FROM backup_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO backup_settings DEFAULT VALUES")

    seed_admin_roles(ADMIN_IDS)
    migrate_passwords()
    migrate_add_name_alias()
    migrate_backup_schedule_columns()
    migrate_pdf_settings_columns()
    migrate_card_batches_columns()

    _create_indexes()


# ─── Re-export stats_snapshots functions ──────────────────────────────
from database.repositories.stats_snapshots import (
    save_snapshot,
    get_yesterday_snapshot,
    get_week_snapshots,
)

# ─── Re-export operator_permissions functions ─────────────────────────
from database.repositories.operator_permissions import (
    assign_router_to_operator,
    revoke_router_from_operator,
    get_operator_routers,
    is_operator_allowed,
)


# ─── Re-exports from cohesive repository modules ──────────────────
from database.repositories.audit_logs import (
    log_action,
    get_logs,
    get_logs_count,
    get_distinct_log_actions,
    get_distinct_log_admins,
    get_distinct_log_routers,
    cleanup_old_logs,
)
from database.repositories.admin_roles import (
    ensure_admin_role,
    seed_admin_roles,
    get_admin_role,
    set_admin_role,
    list_admin_roles,
)
from database.repositories.card_batches import (
    save_card_batch,
    list_card_batches,
    get_card_batch,
    delete_card_batch,
    update_batch_payment,
    get_sales_summary,
)
from database.repositories.user_sessions import (
    get_user_session,
    save_user_session,
)
from database.repositories.pdf_settings import (
    get_pdf_settings,
    update_pdf_settings,
    PDF_ALLOWED_COLUMNS,
)
from database.repositories.routers import (
    save_discovered_router,
    get_saved_routers,
    get_router_by_id,
    get_router_by_ip,
    update_router_credentials,
    update_router_last_seen,
    update_router_identity,
    delete_router,
    update_router_alias,
    get_router_display_name,
)
from database.repositories.backups import (
    get_backup_schedule,
    save_backup_schedule,
    record_backup_result,
    get_last_backup,
    get_recent_backups,
    BACKUP_JOBS_RETENTION_PER_ROUTER,
)
from database.repositories.chat_messages import (
    add_tracked_message,
    get_tracked_messages,
    remove_tracked_messages,
    delete_stale_records,
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
    "get_card_batch",
    "delete_card_batch",
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
]
