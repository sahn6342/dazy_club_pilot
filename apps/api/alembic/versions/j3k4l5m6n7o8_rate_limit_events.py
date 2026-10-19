"""rate_limit_events table (DB-backed rate limiter)

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
"""
import sqlalchemy as sa
from alembic import op

revision = 'j3k4l5m6n7o8'
down_revision = 'i2j3k4l5m6n7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
    )
    op.create_index("ix_rate_limit_events_key", "rate_limit_events", ["key"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_events_key", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
