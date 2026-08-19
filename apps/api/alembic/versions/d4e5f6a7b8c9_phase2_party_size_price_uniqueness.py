"""Phase 2 — party_size (replaces players), price, capacity-aware unique index.

Revision ID: d4e5f6a7b8c9
Revises: cbcc5e7f4b05
Create Date: 2026-06-29

Changes:
  bookings: add party_size + price, backfill party_size from players, drop players.
  Partial unique index: (court_id, slotId) WHERE status NOT IN ('cancelled','no_show')
  — enforces one active booking per court+slot at DB level (capacity=1 guard).
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'cbcc5e7f4b05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: add new nullable columns (simple ADD COLUMN — no table rebuild needed)
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.add_column(sa.Column('party_size', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True))

    # Step 2: backfill party_size from legacy players
    op.execute("UPDATE bookings SET party_size = players WHERE party_size IS NULL")

    # Step 3: make party_size NOT NULL, drop players (full table recreate via batch)
    with op.batch_alter_table('bookings', recreate='always') as batch_op:
        batch_op.alter_column('party_size',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.drop_column('players')

    # Step 4: partial unique index — SQLite supports partial indexes natively
    op.execute(
        'CREATE UNIQUE INDEX uq_active_court_slot '
        'ON bookings(court_id, "slotId") '
        "WHERE status NOT IN ('cancelled', 'no_show')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_court_slot")

    # Restore players as nullable, then backfill, then make NOT NULL
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.add_column(sa.Column('players', sa.Integer(), nullable=True))

    op.execute("UPDATE bookings SET players = party_size WHERE players IS NULL")

    with op.batch_alter_table('bookings', recreate='always') as batch_op:
        batch_op.alter_column('players', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('party_size')
        batch_op.drop_column('price')
