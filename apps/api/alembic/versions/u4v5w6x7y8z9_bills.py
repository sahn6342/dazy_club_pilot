"""bills: counter bills with gap-free numbers

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8
"""
import sqlalchemy as sa
from alembic import op

revision = 'u4v5w6x7y8z9'
down_revision = 't3u4v5w6x7y8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bill_no", sa.String(), nullable=False, unique=True),
        sa.Column("series", sa.String(), nullable=False),
        sa.Column("financial_year", sa.String(), nullable=False),
        sa.Column("bill_date", sa.String(), nullable=False),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("customer_phone", sa.String(), nullable=True),
        sa.Column("customer_gstin", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("booking_ref", sa.String(), nullable=True),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(12, 2), nullable=False),
        sa.Column("sgst", sa.Numeric(12, 2), nullable=False),
        sa.Column("round_off", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_in_words", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("void_reason", sa.String(), nullable=True),
        sa.Column("voided_at", sa.String(), nullable=True),
        sa.Column("voided_by", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_bills_bill_date", "bills", ["bill_date"])
    op.create_index("ix_bills_customer_phone", "bills", ["customer_phone"])
    op.create_table(
        "bill_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bill_id", sa.String(), sa.ForeignKey("bills.id", name="fk_bill_lines_bill"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(12, 2), nullable=False),
        sa.Column("sgst", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])
    op.create_table(
        "bill_sequences",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("bill_sequences")
    op.drop_index("ix_bill_lines_bill_id", table_name="bill_lines")
    op.drop_table("bill_lines")
    op.drop_index("ix_bills_customer_phone", table_name="bills")
    op.drop_index("ix_bills_bill_date", table_name="bills")
    op.drop_table("bills")
