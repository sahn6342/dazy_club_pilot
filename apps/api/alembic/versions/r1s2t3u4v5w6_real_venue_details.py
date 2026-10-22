"""real venue address, phone and hours instead of the seeded placeholders

Only CMS rows that still hold the original placeholder text are changed: anything an admin has already edited
in Admin -> Contact Details is left alone. Safe to run more than once.

Revision ID: r1s2t3u4v5w6
Revises: q0r1s2t3u4v5
"""
import sqlalchemy as sa
from alembic import op

revision = 'r1s2t3u4v5w6'
down_revision = 'q0r1s2t3u4v5'
branch_labels = None
depends_on = None

# (cms key, old placeholder, real value)
_CHANGES = [
    ("venue_address", "123 Sports Complex, Bengaluru, Karnataka 560001",
     "J29M+RP5 D1, Chamari Chak Rd, Ram Krishna Puram, Balaji Nagar, New Tarachak, Danapur, Patna, Bihar 801503"),
    ("venue_phone", "+91 98765 43210", "+91 93153 06294"),
    ("venue_hours", "Mon–Sun: 6:00 AM – 10:00 PM", "Open 24 hours"),
    ("whatsapp_phone", "919876543211", "919315306294"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for key, old, new in _CHANGES:
        bind.execute(
            sa.text("UPDATE cms SET value = :new WHERE key = :key AND value = :old"),
            {"new": new, "key": key, "old": old},
        )


def downgrade() -> None:
    # The placeholders were never real data; nothing to restore.
    pass
