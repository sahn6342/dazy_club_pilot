"""Phase 3 — customers table + bookings.customer_id.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-29

Changes:
  new table: customers (id, name, phone UNIQUE, email, createdAt)
  bookings: add customer_id (nullable, soft FK — not enforced at SQLite level)
  Status enum in application layer expanded to: pending|confirmed|completed|cancelled|no_show
  (no DB change needed for status — stored as plain string)
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'customers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),   # primary contact (phone or email)
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('createdAt', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone', name='uq_customers_phone'),
    )
    op.create_index('ix_customers_phone', 'customers', ['phone'], unique=True)

    with op.batch_alter_table('bookings') as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.String(), nullable=True))

    op.create_index('ix_bookings_customer_id', 'bookings', ['customer_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_bookings_customer_id', table_name='bookings')
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.drop_column('customer_id')
    op.drop_index('ix_customers_phone', table_name='customers')
    op.drop_table('customers')
