"""court_sports: one court can serve several sports (football shares the cricket turf)

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4
"""
import sqlalchemy as sa
from alembic import op

revision = 'q0r1s2t3u4v5'
down_revision = 'p9q0r1s2t3u4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "court_sports",
        sa.Column("court_id", sa.String(), sa.ForeignKey("courts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sport_slug", sa.String(), primary_key=True),
    )
    op.create_index("ix_court_sports_sport_slug", "court_sports", ["sport_slug"])
    # Every court serves its own sport...
    op.execute("INSERT INTO court_sports (court_id, sport_slug) SELECT id, sport FROM courts")
    # ...and football is played on the cricket turf (same court, so a booking under either sport blocks the other).
    op.execute(
        "INSERT INTO court_sports (court_id, sport_slug) "
        "SELECT id, 'football' FROM courts WHERE id = 'court-cricket'"
    )


def downgrade() -> None:
    op.drop_index("ix_court_sports_sport_slug", table_name="court_sports")
    op.drop_table("court_sports")
