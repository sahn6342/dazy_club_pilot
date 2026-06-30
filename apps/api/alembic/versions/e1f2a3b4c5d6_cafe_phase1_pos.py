"""Café POS Phase 1 — orders, order_items, kots, payments, invoices, invoice_lines, invoice_sequences.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-30

Adds POS core tables.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("orderNo", sa.String(), nullable=False, unique=True),
        sa.Column("orderType", sa.String(), nullable=False),
        sa.Column("table_id", sa.String(), sa.ForeignKey("cafe_tables.id"), nullable=True),
        sa.Column("customer_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("discountAmount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("taxAmount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("roundOff", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("createdBy", sa.String(), nullable=False),
        sa.Column("createdAt", sa.String(), nullable=False),
        sa.Column("updatedAt", sa.String(), nullable=False),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("menu_item_id", sa.String(), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("kot_id", sa.String(), nullable=True),
        sa.Column("nameSnapshot", sa.String(), nullable=False),
        sa.Column("qty", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unitPrice", sa.Numeric(10, 2), nullable=False),
        sa.Column("taxRatePercent", sa.Numeric(5, 2), nullable=False, server_default="5"),
        sa.Column("hsnSacSnapshot", sa.String(), nullable=True),
        sa.Column("lineSubtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("lineTax", sa.Numeric(10, 2), nullable=False),
        sa.Column("lineTotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("kotStatus", sa.String(), nullable=True),
        sa.Column("voided", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("voidReason", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.String(), nullable=False),
    )

    op.create_table(
        "kots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kotNo", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("station", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("printedAt", sa.String(), nullable=True),
        sa.Column("createdAt", sa.String(), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("createdBy", sa.String(), nullable=False),
        sa.Column("createdAt", sa.String(), nullable=False),
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoiceNo", sa.String(), nullable=False),
        sa.Column("invoiceType", sa.String(), nullable=False),
        sa.Column("series", sa.String(), nullable=False),
        sa.Column("financialYear", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("customerName", sa.String(), nullable=True),
        sa.Column("customerGstin", sa.String(), nullable=True),
        sa.Column("taxableValue", sa.Numeric(10, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(10, 2), nullable=False),
        sa.Column("sgst", sa.Numeric(10, 2), nullable=False),
        sa.Column("roundOff", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("amountInWords", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="issued"),
        sa.Column("issuedBy", sa.String(), nullable=False),
        sa.Column("issuedAt", sa.String(), nullable=False),
    )

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("hsnSac", sa.String(), nullable=True),
        sa.Column("qty", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("taxableValue", sa.Numeric(10, 2), nullable=False),
        sa.Column("gstRatePercent", sa.Numeric(5, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(10, 2), nullable=False),
        sa.Column("sgst", sa.Numeric(10, 2), nullable=False),
        sa.Column("lineTotal", sa.Numeric(10, 2), nullable=False),
    )

    op.create_table(
        "invoice_sequences",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("series", sa.String(), nullable=False),
        sa.Column("financialYear", sa.String(), nullable=False),
        sa.Column("lastNumber", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("invoice_sequences")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("payments")
    op.drop_table("kots")
    op.drop_table("order_items")
    op.drop_table("orders")
