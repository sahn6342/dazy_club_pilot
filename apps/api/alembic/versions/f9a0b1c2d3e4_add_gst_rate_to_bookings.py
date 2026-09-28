"""Add gst_rate_percent to bookings — snapshot GST rate at booking time.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'f9a0b1c2d3e4'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.add_column(sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_column("gst_rate_percent")
