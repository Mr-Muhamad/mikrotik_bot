"""Add duration_ms and error_category columns to logs table.

Revision ID: c8d4e2f3a567
Revises: b3e7f1d2a890
"""

import sqlalchemy as sa

from alembic import op

revision = "c8d4e2f3a567"
down_revision = "b3e7f1d2a890"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("logs")]
    if "duration_ms" not in existing_columns:
        op.add_column("logs", sa.Column("duration_ms", sa.Float))
    if "error_category" not in existing_columns:
        op.add_column("logs", sa.Column("error_category", sa.String, default=""))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("logs")]
    if "error_category" in existing_columns:
        op.drop_column("logs", "error_category")
    if "duration_ms" in existing_columns:
        op.drop_column("logs", "duration_ms")
