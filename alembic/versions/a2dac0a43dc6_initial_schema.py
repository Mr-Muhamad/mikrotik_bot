"""initial schema

Revision ID: a2dac0a43dc6
Revises:
Create Date: 2026-07-19 12:53:17.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from config import DEFAULT_API_PORT


# revision identifiers, used by Alembic.
revision: str = "a2dac0a43dc6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── TABLES ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            username TEXT,
            router_name TEXT,
            admin_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_roles (
            admin_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            changed_by INTEGER,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            customer_name TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'unpaid',
            sale_price REAL DEFAULT 0,
            sold_at DATETIME
        )
    """)

    op.execute("""
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

    op.execute("""
        CREATE TABLE IF NOT EXISTS backup_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_dir TEXT DEFAULT './backups',
            send_telegram INTEGER DEFAULT 1,
            save_local INTEGER DEFAULT 1,
            schedule_enabled INTEGER DEFAULT 0,
            schedule_hour INTEGER DEFAULT 3,
            schedule_minute INTEGER DEFAULT 0
        )
    """)

    op.execute("""
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

    op.execute("""
        CREATE TABLE IF NOT EXISTS router_health_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            router_key TEXT NOT NULL,
            status TEXT NOT NULL,
            checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            error_msg TEXT DEFAULT ''
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tracked_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            tracked_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
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

    op.execute("""
        CREATE TABLE IF NOT EXISTS operator_router_permissions (
            operator_id INTEGER NOT NULL,
            router_id INTEGER NOT NULL,
            assigned_by INTEGER,
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (operator_id, router_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER PRIMARY KEY,
            selected_router TEXT DEFAULT 'router1',
            current_action TEXT,
            action_data TEXT,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_timeout INTEGER DEFAULT 600
        )
    """)

    op.execute(f"""
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
            name_alias TEXT DEFAULT '',
            owner_id INTEGER DEFAULT 0
        )
    """)

    # ─── INDEXES ─────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_logs_admin ON logs(admin_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_routers_active ON discovered_routers(is_active, added_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_routers_ip ON discovered_routers(ip_address)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_backup_jobs_router ON backup_jobs(router_key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_backup_jobs_created ON backup_jobs(created_at DESC)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_health_router_time ON router_health_log(router_key, checked_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_snapshots_router_date ON stats_snapshots(router_key, snapshot_date DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_tracked_messages_chat ON tracked_messages(chat_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tracked_messages_date ON tracked_messages(tracked_at)"
    )

    # ─── DEFAULT VALUES ──────────────────────────────────────────
    op.execute("""
        INSERT INTO pdf_settings (id)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM pdf_settings)
    """)
    op.execute("""
        INSERT INTO backup_settings (id)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM backup_settings)
    """)


def downgrade() -> None:
    pass
