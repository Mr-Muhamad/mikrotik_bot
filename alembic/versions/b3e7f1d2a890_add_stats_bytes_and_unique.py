"""Add bytes_in/bytes_out to stats_snapshots and unique constraint.

Revision ID: b3e7f1d2a890
Revises: a2dac0a43dc6
"""

from alembic import op
import sqlalchemy as sa

revision = "b3e7f1d2a890"
down_revision = "a2dac0a43dc6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("stats_snapshots")]
    if "bytes_in" not in existing_columns:
        op.add_column("stats_snapshots", sa.Column("bytes_in", sa.Integer, server_default=sa.text("0")))
    if "bytes_out" not in existing_columns:
        op.add_column("stats_snapshots", sa.Column("bytes_out", sa.Integer, server_default=sa.text("0")))
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_snapshots_router_date "
        "ON stats_snapshots(router_key, snapshot_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_snapshots_router_date")
    op.drop_column("stats_snapshots", "bytes_out")
    op.drop_column("stats_snapshots", "bytes_in")
