"""Phase 3 (Roadmap) — booking payment status + booking_payments table.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-02

Online prepay for court bookings. `booking_payments` keys off `bookingRef`
(not a single row id) because a multi-slot booking is several BookingRows
sharing one ref, paid for together as one payment.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b5c6d7e8f9a0'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.add_column(sa.Column("paymentStatus", sa.String(), nullable=False, server_default="unpaid"))
        b.add_column(sa.Column("depositAmount", sa.Numeric(10, 2), nullable=True))

    op.create_table(
        "booking_payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bookingRef", sa.String(), nullable=False, index=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("providerOrderId", sa.String(), nullable=False, index=True),
        sa.Column("providerPaymentId", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("createdAt", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("booking_payments")
    with op.batch_alter_table("bookings", recreate="always") as b:
        b.drop_column("depositAmount")
        b.drop_column("paymentStatus")
