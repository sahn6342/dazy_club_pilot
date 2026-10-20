"""admin scale: bookings soft delete, contact_norm and the indexes the hot queries need

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
"""
import sqlalchemy as sa
from alembic import op

revision = 'n7o8p9q0r1s2'
down_revision = 'm6n7o8p9q0r1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as b:
        b.add_column(sa.Column("contact_norm", sa.String(), nullable=True))
        b.add_column(sa.Column("deleted_at", sa.String(), nullable=True))
        b.add_column(sa.Column("deleted_by", sa.String(), nullable=True))
    op.execute("UPDATE bookings SET contact_norm = lower(trim(contact))")
    # bookingRef was never indexed although payment, lookup and notification paths all filter on it.
    op.create_index("ix_bookings_bookingRef", "bookings", ["bookingRef"])
    op.create_index("ix_bookings_contact_norm", "bookings", ["contact_norm"])
    op.create_index("ix_bookings_date_status", "bookings", ["date", "status"])
    op.create_index("ix_bookings_status_created", "bookings", ["status", "createdAt"])
    op.execute("CREATE INDEX ix_bookings_email_lower ON bookings (lower(email))")
    op.create_index("ix_enquiries_createdAt", "enquiries", ["createdAt"])
    op.create_index("ix_customers_createdAt", "customers", ["createdAt"])


def downgrade() -> None:
    op.drop_index("ix_customers_createdAt", table_name="customers")
    op.drop_index("ix_enquiries_createdAt", table_name="enquiries")
    op.execute("DROP INDEX IF EXISTS ix_bookings_email_lower")
    op.drop_index("ix_bookings_status_created", table_name="bookings")
    op.drop_index("ix_bookings_date_status", table_name="bookings")
    op.drop_index("ix_bookings_contact_norm", table_name="bookings")
    op.drop_index("ix_bookings_bookingRef", table_name="bookings")
    with op.batch_alter_table("bookings") as b:
        b.drop_column("deleted_by")
        b.drop_column("deleted_at")
        b.drop_column("contact_norm")
