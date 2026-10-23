"""advance payments: record the balance collected at the venue

The advance itself needs no column (bookings.depositAmount already exists). These four fields record the
rest of the money, taken at the venue, against the booking's primary row.

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
"""
import sqlalchemy as sa
from alembic import op

revision = 's2t3u4v5w6x7'
down_revision = 'r1s2t3u4v5w6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as b:
        b.add_column(sa.Column("balance_collected", sa.Numeric(10, 2), nullable=False, server_default="0"))
        b.add_column(sa.Column("balance_mode", sa.String(), nullable=True))
        b.add_column(sa.Column("balance_collected_at", sa.String(), nullable=True))
        b.add_column(sa.Column("balance_collected_by", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bookings") as b:
        b.drop_column("balance_collected_by")
        b.drop_column("balance_collected_at")
        b.drop_column("balance_mode")
        b.drop_column("balance_collected")
