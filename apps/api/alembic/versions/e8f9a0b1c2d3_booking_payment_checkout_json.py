"""Booking self-service lookup/resume — store the checkout payload.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-03

Lets GET /bookings/lookup resume a pending payment with the SAME checkout
order that was already created — never a second Razorpay order for one
booking. `checkoutJson` is the opaque `PaymentOrder.checkout` dict, verbatim.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("booking_payments") as batch_op:
        batch_op.add_column(sa.Column("checkoutJson", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("booking_payments") as batch_op:
        batch_op.drop_column("checkoutJson")
