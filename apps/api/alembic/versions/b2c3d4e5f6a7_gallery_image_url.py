"""Phase 5b — gallery.imageUrl column.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-30

Changes:
  gallery: add imageUrl (String, nullable). Holds either an absolute URL
  (pasted) or a relative path like /media/gallery/<uuid>.<ext> (uploaded file).
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("gallery", recreate="always") as b:
        b.add_column(sa.Column("imageUrl", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("gallery", recreate="always") as b:
        b.drop_column("imageUrl")
