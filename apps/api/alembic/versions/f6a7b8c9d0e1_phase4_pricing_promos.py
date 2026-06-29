"""Phase 4 — pricing + promo codes.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-29

Changes:
  schedule_rules: add discount_percent (Integer, nullable, 0..100)
  bookings: add promo_code (String, nullable)
  new table: promo_codes (code UNIQUE, kind percent|flat, value, validity, usage caps, sport scope)
  data backfill: default base prices on existing rules by sport (cricket 1200, badminton 500, pickleball 700)
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None

_DEFAULT_PRICE = {"cricket": 1200, "badminton": 500, "pickleball": 700}


def upgrade() -> None:
    with op.batch_alter_table("schedule_rules", recreate="always") as b:
        b.add_column(sa.Column("discount_percent", sa.Integer(), nullable=True))
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.add_column(sa.Column("promo_code", sa.String(), nullable=True))

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.String(), nullable=True),
        sa.Column("valid_to", sa.String(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("sport_slug", sa.String(), nullable=True),
        sa.Column("createdAt", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"], unique=True)

    # Backfill default base prices on existing rules (idempotent on price IS NULL).
    conn = op.get_bind()
    for sport, price in _DEFAULT_PRICE.items():
        conn.execute(
            sa.text("UPDATE schedule_rules SET price=:p WHERE price IS NULL AND court_id=:c"),
            {"p": price, "c": f"court-{sport}"},
        )


def downgrade() -> None:
    op.drop_index("ix_promo_codes_code", table_name="promo_codes")
    op.drop_table("promo_codes")
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.drop_column("promo_code")
    with op.batch_alter_table("schedule_rules", recreate="always") as b:
        b.drop_column("discount_percent")
    # Base-price backfill is additive data — intentionally not reverted.
