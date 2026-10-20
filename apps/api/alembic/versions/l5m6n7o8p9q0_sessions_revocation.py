"""users.token_version and revoked_tokens (session revocation)

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
"""
import sqlalchemy as sa
from alembic import op

revision = 'l5m6n7o8p9q0'
down_revision = 'k4l5m6n7o8p9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(), primary_key=True),
        sa.Column("exp", sa.Float(), nullable=False),
    )
    op.create_index("ix_revoked_tokens_exp", "revoked_tokens", ["exp"])


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_exp", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    with op.batch_alter_table("users") as b:
        b.drop_column("token_version")
