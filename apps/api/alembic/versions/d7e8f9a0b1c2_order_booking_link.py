"""Phase 7 (Detailed-Roadmap) — link a cafe order to a booking (pre-order).

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-02

Lets a customer add cafe items to their slot: `orders.booking_id` is a soft
link to bookings.id (nullable — most orders are still walk-in POS sales with
no associated booking).
"""
from alembic import op
import sqlalchemy as sa

revision = 'd7e8f9a0b1c2'
down_revision = 'c6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("booking_id", sa.String(), nullable=True))
    op.create_index("ix_orders_booking_id", "orders", ["booking_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_booking_id", table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("booking_id")
