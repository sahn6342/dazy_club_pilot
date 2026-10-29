"""counter (walk-in) bookings: source, payment mode and who took the booking

Online bookings keep source='online'. A booking taken at the counter by staff is source='counter', is
confirmed and paid on creation, and records how the money was received (cash/upi) with no gateway payment.

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
"""
import sqlalchemy as sa
from alembic import op

revision = 't3u4v5w6x7y8'
down_revision = 's2t3u4v5w6x7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as b:
        b.add_column(sa.Column("source", sa.String(), nullable=False, server_default="online"))
        b.add_column(sa.Column("payment_mode", sa.String(), nullable=True))
        b.add_column(sa.Column("payment_reference", sa.String(), nullable=True))
        b.add_column(sa.Column("created_by", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bookings") as b:
        b.drop_column("created_by")
        b.drop_column("payment_reference")
        b.drop_column("payment_mode")
        b.drop_column("source")
