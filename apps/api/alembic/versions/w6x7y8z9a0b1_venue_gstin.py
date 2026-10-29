"""venue GSTIN lives in Contact Details (CMS key venue_gstin), printed on bills

Existing databases get the empty entry so the Contact Details page shows the field. A brand-new database is left
alone: its CMS table is still empty here and the seed fills it, including this key.

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
"""
import sqlalchemy as sa
from alembic import op

revision = 'w6x7y8z9a0b1'
down_revision = 'v5w6x7y8z9a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT COUNT(*) FROM cms")).scalar():
        conn.execute(sa.text(
            "INSERT INTO cms (key, label, value) SELECT :k, :l, :v "
            "WHERE NOT EXISTS (SELECT 1 FROM cms WHERE key = :k)"
        ), {"k": "venue_gstin", "l": "GSTIN (printed on bills)", "v": ""})


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM cms WHERE key = :k"), {"k": "venue_gstin"})
