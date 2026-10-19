"""otp_codes table (customer OTP for contact-only booking search)

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
"""
import sqlalchemy as sa
from alembic import op

revision = 'k4l5m6n7o8p9'
down_revision = 'j3k4l5m6n7o8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("contact", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_otp_codes_contact", "otp_codes", ["contact"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_otp_codes_contact", table_name="otp_codes")
    op.drop_table("otp_codes")
