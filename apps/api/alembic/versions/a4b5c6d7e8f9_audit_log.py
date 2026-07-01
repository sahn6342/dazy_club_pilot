"""Phase 1 (Roadmap) — audit_log table.

Revision ID: a4b5c6d7e8f9
Revises: e1f2a3b4c5d6
Create Date: 2026-07-01

Records sensitive admin/cashier actions (logins, booking status changes,
user CRUD, settings updates, password resets) for traceability.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a4b5c6d7e8f9'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("at", sa.String(), nullable=False, index=True),
        sa.Column("actor", sa.String(), nullable=False, index=True),
        sa.Column("actorRole", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False, index=True),
        sa.Column("entityType", sa.String(), nullable=True),
        sa.Column("entityId", sa.String(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
