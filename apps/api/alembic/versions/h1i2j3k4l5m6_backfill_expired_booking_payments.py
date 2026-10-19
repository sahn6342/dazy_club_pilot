"""backfill booking_payments.status='expired' for timed-out unpaid bookings

mark_expired_by_refs used to filter status 'pending' while rows were created as
'created', so expired payment rows were never flipped.

Revision ID: h1i2j3k4l5m6
Revises: g0h1i2j3k4l5
"""
from alembic import op

revision = 'h1i2j3k4l5m6'
down_revision = 'g0h1i2j3k4l5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE booking_payments SET status = 'expired' "
        "WHERE status = 'created' AND \"bookingRef\" IN ("
        "SELECT \"bookingRef\" FROM bookings "
        "WHERE is_primary = true AND status = 'cancelled' AND \"paymentStatus\" = 'unpaid')"
    )


def downgrade() -> None:
    pass  # data-only fix; nothing to restore
