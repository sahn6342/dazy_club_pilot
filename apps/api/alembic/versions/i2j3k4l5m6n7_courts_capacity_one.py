"""force courts.capacity = 1 (one court = one booking per slot)

The unique index uq_active_court_slot already allows only one active booking per
court+slot, so capacity > 1 could never work: availability said "free" and the
insert then failed with a 409.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
"""
from alembic import op

revision = 'i2j3k4l5m6n7'
down_revision = 'h1i2j3k4l5m6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE courts SET capacity = 1 WHERE capacity <> 1")


def downgrade() -> None:
    pass  # previous values are not recoverable (and were never honoured)
