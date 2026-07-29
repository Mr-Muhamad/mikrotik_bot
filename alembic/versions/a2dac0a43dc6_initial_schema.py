"""Initial schema migration for MikroTik Telegram Bot.

Creates all core tables and columns required by the application.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a2dac0a43dc6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_routers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ip_address", sa.String, unique=True, nullable=False),
        sa.Column("mac_address", sa.String, default=""),
        sa.Column("identity", sa.String, default="Unknown"),
        sa.Column("version", sa.String, default=""),
        sa.Column("board", sa.String, default=""),
        sa.Column("software_id", sa.String, default=""),
        sa.Column("platform", sa.String, default="MikroTik"),
        sa.Column("uptime", sa.String, default=""),
        sa.Column("port", sa.Integer, default=8728),
        sa.Column("username", sa.String, default=""),
        sa.Column("password", sa.String, default=""),
        sa.Column("last_seen", sa.String, default=""),
        sa.Column("added_at", sa.String, default=""),
        sa.Column("is_active", sa.Integer, server_default=sa.text("1")),
        sa.Column("name_alias", sa.String, default=""),
        sa.Column("owner_id", sa.Integer, default=0),
    )
    op.create_index(
        "idx_routers_ip", "discovered_routers", ["ip_address"]
    )
    op.create_index(
        "idx_routers_active", "discovered_routers", ["is_active", "added_at"]
    )

    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Integer, primary_key=True),
        sa.Column("selected_router", sa.String, default=""),
        sa.Column("current_action", sa.String, default=""),
        sa.Column("action_data", sa.String, default=""),
        sa.Column("last_activity", sa.DateTime, server_default=sa.func.now()),
        sa.Column("session_timeout", sa.Integer, default=600),
    )
    op.create_index(
        "idx_sessions_user", "user_sessions", ["user_id"]
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("username", sa.String, default=""),
        sa.Column("router_name", sa.String, default=""),
        sa.Column("admin_id", sa.Integer),
        sa.Column("timestamp", sa.String, default=""),
    )
    op.create_index("idx_logs_admin", "logs", ["admin_id"])
    op.create_index("idx_logs_timestamp", "logs", ["timestamp"])

    op.create_table(
        "admin_roles",
        sa.Column("admin_id", sa.Integer, primary_key=True),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("changed_by", sa.Integer),
        sa.Column("changed_at", sa.String, default=""),
    )

    op.create_table(
        "card_batches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("router_key", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("batch_type", sa.String, nullable=False),
        sa.Column("profile", sa.String, default=""),
        sa.Column("comment_prefix", sa.String, default=""),
        sa.Column("count", sa.Integer, default=0),
        sa.Column("cards_json", sa.String, default=""),
        sa.Column("created_by", sa.Integer),
        sa.Column("created_at", sa.String, default=""),
        sa.Column("customer_name", sa.String, default=""),
        sa.Column("payment_status", sa.String, default="unpaid"),
        sa.Column("sale_price", sa.Float, default=0.0),
        sa.Column("sold_at", sa.DateTime),
    )

    op.create_table(
        "pdf_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("margin_top", sa.Integer, default=10),
        sa.Column("margin_bottom", sa.Integer, default=10),
        sa.Column("margin_left", sa.Integer, default=10),
        sa.Column("margin_right", sa.Integer, default=10),
        sa.Column("border_width", sa.Float, default=1.0),
        sa.Column("card_width", sa.Float, default=90.0),
        sa.Column("card_height", sa.Float, default=54.0),
        sa.Column("spacing_x", sa.Float, default=5.0),
        sa.Column("spacing_y", sa.Float, default=5.0),
        sa.Column("cards_per_row", sa.Integer, default=2),
        sa.Column("cards_per_page", sa.Integer, default=40),
        sa.Column("footer_text", sa.String, default=""),
        sa.Column("header_text", sa.String, default=""),
        sa.Column("brand_name", sa.String, default=""),
        sa.Column("hotspot_dns", sa.String, default=""),
        sa.Column("show_qr", sa.Integer, default=1),
        sa.Column("label_spacing_single", sa.Float, default=1.0),
        sa.Column("label_spacing_dual", sa.Float, default=1.0),
        sa.Column("value_max_font_single", sa.Integer, default=12),
        sa.Column("value_max_font_dual", sa.Integer, default=11),
    )

    op.create_table(
        "backup_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("schedule_enabled", sa.Integer, default=0),
        sa.Column("schedule_hour", sa.Integer, default=3),
        sa.Column("schedule_minute", sa.Integer, default=0),
    )

    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("router_key", sa.String, nullable=False),
        sa.Column("router_name", sa.String, default=""),
        sa.Column("backup_type", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("details", sa.String, default=""),
        sa.Column("file_name", sa.String, default=""),
        sa.Column("created_at", sa.String, default=""),
    )
    op.create_index(
        "idx_backup_jobs_router", "backup_jobs", ["router_key"]
    )
    op.create_index(
        "idx_backup_jobs_created", "backup_jobs", ["created_at"]
    )

    op.create_table(
        "router_health_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("router_key", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("checked_at", sa.String, default=""),
        sa.Column("error_msg", sa.String, default=""),
    )
    op.create_index(
        "idx_health_router_time", "router_health_log", ["router_key", "checked_at"]
    )

    op.create_table(
        "stats_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("router_key", sa.String, nullable=False),
        sa.Column("snapshot_date", sa.String, default=""),
        sa.Column("active_users", sa.Integer, default=0),
        sa.Column("total_users", sa.Integer, default=0),
    )
    op.create_index(
        "idx_snapshots_router_date", "stats_snapshots", ["router_key", "snapshot_date"]
    )

    op.create_table(
        "tracked_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.Integer, nullable=False),
        sa.Column("message_id", sa.Integer, nullable=False),
        sa.Column("tracked_at", sa.String, default=""),
    )
    op.create_index(
        "idx_tracked_messages_chat", "tracked_messages", ["chat_id"]
    )
    op.create_index(
        "idx_tracked_messages_date", "tracked_messages", ["tracked_at"]
    )

    op.create_table(
        "operator_router_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("operator_id", sa.Integer, nullable=False),
        sa.Column("router_id", sa.Integer, nullable=False),
        sa.Column("assigned_by", sa.Integer),
        sa.Column("assigned_at", sa.String, default=""),
    )
    # Insert default singleton rows for settings tables
    op.execute(
        "INSERT OR IGNORE INTO pdf_settings (id, margin_top, margin_bottom, margin_left, margin_right, border_width, card_width, card_height, spacing_x, spacing_y, cards_per_row, cards_per_page, footer_text, header_text, brand_name, hotspot_dns, show_qr, label_spacing_single, label_spacing_dual, value_max_font_single, value_max_font_dual) VALUES (1, 10, 10, 10, 10, 1.0, 90.0, 54.0, 5.0, 5.0, 4, 40, '', '', '', '', 1, 1.0, 1.0, 12, 11)"
    )
    op.execute(
        "INSERT OR IGNORE INTO backup_settings (id, schedule_enabled, schedule_hour, schedule_minute) VALUES (1, 0, 3, 0)"
    )


def downgrade() -> None:
    op.drop_table("operator_router_permissions")
    op.drop_table("tracked_messages")
    op.drop_table("stats_snapshots")
    op.drop_table("router_health_log")
    op.drop_table("backup_jobs")
    op.drop_table("backup_settings")
    op.drop_table("pdf_settings")
    op.drop_table("card_batches")
    op.drop_table("admin_roles")
    op.drop_table("logs")
    op.drop_table("user_sessions")
    op.drop_table("discovered_routers")
