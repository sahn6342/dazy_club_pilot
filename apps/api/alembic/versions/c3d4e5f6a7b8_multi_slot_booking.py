"""Multi-slot booking support — add is_primary flag to bookings.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-30

Changes:
  bookings: add is_primary (Boolean, NOT NULL, default True).
  Primary row carries price/promo/message; secondary rows hold the remaining
  slot locks and share bookingRef. get_all() filters to is_primary=True so
  the admin list sees one entry per booking regardless of slot count.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.add_column(sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.drop_column("is_primary")
