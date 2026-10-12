"""Add email to bookings — optional customer email captured at booking time.

Revision ID: g0h1i2j3k4l5
Revises: f9a0b1c2d3e4
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'g0h1i2j3k4l5'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_column("email")
