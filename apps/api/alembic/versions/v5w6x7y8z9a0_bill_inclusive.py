"""bills: prices include GST

Bills issued so far took the rate excluding GST (prices_include_tax = false, kept as is). New bills take the rate
including GST and are saved with prices_include_tax = true.

Revision ID: v5w6x7y8z9a0
Revises: u4v5w6x7y8z9
"""
import sqlalchemy as sa
from alembic import op

revision = 'v5w6x7y8z9a0'
down_revision = 'u4v5w6x7y8z9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bills") as b:
        b.add_column(sa.Column("prices_include_tax", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("bills") as b:
        b.drop_column("prices_include_tax")
