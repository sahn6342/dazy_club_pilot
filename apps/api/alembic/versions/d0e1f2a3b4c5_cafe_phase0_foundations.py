"""Café POS Phase 0 — foundation tables.

Revision ID: d0e1f2a3b4c5
Revises: c3d4e5f6a7b8
Create Date: 2026-06-30

Adds: cafe_settings, menu_categories, menu_items, cafe_tables.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd0e1f2a3b4c5'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cafe_settings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("legalName", sa.String(), nullable=True),
        sa.Column("gstin", sa.String(), nullable=True),
        sa.Column("fssaiNumber", sa.String(), nullable=True),
        sa.Column("addressLine", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("stateName", sa.String(), nullable=True),
        sa.Column("stateCode", sa.String(), nullable=True),
        sa.Column("scheme", sa.String(), nullable=False, server_default="regular"),
        sa.Column("priceIncludesTax", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("defaultTaxRate", sa.Numeric(5, 2), nullable=False, server_default="5.0"),
        sa.Column("invoiceSeriesPrefix", sa.String(), nullable=False, server_default="INV"),
        sa.Column("billOfSupplySeriesPrefix", sa.String(), nullable=False, server_default="BOS"),
        sa.Column("logoUrl", sa.String(), nullable=True),
        sa.Column("declaration", sa.Text(), nullable=True),
        sa.Column("footerNote", sa.Text(), nullable=True),
        sa.Column("roundingEnabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("createdAt", sa.String(), nullable=False),
        sa.Column("updatedAt", sa.String(), nullable=False),
    )

    op.create_table(
        "menu_categories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("vegType", sa.String(), nullable=True),
        sa.Column("sortOrder", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("createdAt", sa.String(), nullable=False),
    )

    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("category_id", sa.String(), sa.ForeignKey("menu_categories.id"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("taxRatePercent", sa.Numeric(5, 2), nullable=False, server_default="5.0"),
        sa.Column("hsnSac", sa.String(), nullable=True),
        sa.Column("vegType", sa.String(), nullable=True),
        sa.Column("isPackaged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("station", sa.String(), nullable=False, server_default="kitchen"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("trackInventory", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("currentQty", sa.Numeric(10, 3), nullable=True),
        sa.Column("reorderLevel", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("purchaseCost", sa.Numeric(10, 2), nullable=True),
        sa.Column("barcode", sa.String(), nullable=True),
        sa.Column("imageUrl", sa.String(), nullable=True),
        sa.Column("sortOrder", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("createdAt", sa.String(), nullable=False),
    )

    op.create_table(
        "cafe_tables",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("status", sa.String(), nullable=False, server_default="free"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sortOrder", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("cafe_tables")
    op.drop_table("menu_items")
    op.drop_table("menu_categories")
    op.drop_table("cafe_settings")
