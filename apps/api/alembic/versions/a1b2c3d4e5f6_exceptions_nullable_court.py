"""Phase 5a — schedule_exceptions.court_id nullable (venue-wide holidays).

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-06-30

Changes:
  schedule_exceptions.court_id -> nullable. NULL means the exception applies
  venue-wide (all courts). A holiday closure on NULL closes every court that day.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("schedule_exceptions", recreate="always") as b:
        b.alter_column("court_id", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Backfill any venue-wide (NULL) exceptions to the first court so the column
    # can become NOT NULL again.
    conn = op.get_bind()
    first_court = conn.execute(sa.text("SELECT id FROM courts ORDER BY id LIMIT 1")).scalar()
    if first_court is not None:
        conn.execute(
            sa.text("UPDATE schedule_exceptions SET court_id = :cid WHERE court_id IS NULL"),
            {"cid": first_court},
        )
    with op.batch_alter_table("schedule_exceptions", recreate="always") as b:
        b.alter_column("court_id", existing_type=sa.String(), nullable=False)
