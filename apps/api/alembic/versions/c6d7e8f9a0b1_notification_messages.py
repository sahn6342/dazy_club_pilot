"""Phase 5 (Detailed-Roadmap) — notification_messages delivery log.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-02

Auditable outbound-notification log (DEC-026). One row per send attempt —
success, skip, or failure — never a launch-blocker for the flow that
triggered it (see services/notification_service.py).
"""
from alembic import op
import sqlalchemy as sa

revision = 'c6d7e8f9a0b1'
down_revision = 'b5c6d7e8f9a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("refType", sa.String(), nullable=False, index=True),
        sa.Column("refId", sa.String(), nullable=False, index=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("recipient", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("errorMessage", sa.String(), nullable=True),
        sa.Column("createdAt", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_messages")
