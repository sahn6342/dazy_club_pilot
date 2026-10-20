"""booking_payments.refunded_amount (partial refunds) and the default refund policy

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
"""
import sqlalchemy as sa
from alembic import op

revision = 'm6n7o8p9q0r1'
down_revision = 'l5m6n7o8p9q0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("booking_payments") as b:
        b.add_column(sa.Column("refunded_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    # Payments already refunded in full before partial refunds existed.
    op.execute("UPDATE booking_payments SET refunded_amount = amount WHERE status = 'refunded'")


def downgrade() -> None:
    with op.batch_alter_table("booking_payments") as b:
        b.drop_column("refunded_amount")
