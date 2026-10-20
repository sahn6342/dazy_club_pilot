"""notification_messages becomes an outbox: payload, attempts, next_attempt_at (retries)

Revision ID: p9q0r1s2t3u4
Revises: o8p9q0r1s2t3
"""
import sqlalchemy as sa
from alembic import op

revision = 'p9q0r1s2t3u4'
down_revision = 'o8p9q0r1s2t3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_messages") as b:
        b.add_column(sa.Column("event", sa.String(), nullable=True))
        b.add_column(sa.Column("payload", sa.Text(), nullable=True))
        b.add_column(sa.Column("provider", sa.String(), nullable=True))
        b.add_column(sa.Column("provider_ref", sa.String(), nullable=True))
        b.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"))
        b.add_column(sa.Column("last_attempt_at", sa.String(), nullable=True))
        b.add_column(sa.Column("next_attempt_at", sa.String(), nullable=True))
    op.create_index("ix_notification_messages_status", "notification_messages", ["status"])
    op.create_index("ix_notification_messages_next_attempt_at", "notification_messages", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_messages_next_attempt_at", table_name="notification_messages")
    op.drop_index("ix_notification_messages_status", table_name="notification_messages")
    with op.batch_alter_table("notification_messages") as b:
        for col in ("next_attempt_at", "last_attempt_at", "attempts", "provider_ref", "provider", "payload", "event"):
            b.drop_column(col)
