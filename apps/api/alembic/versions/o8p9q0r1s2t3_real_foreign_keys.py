"""real foreign keys on bookings and orders (they were "soft" ids with no constraint)

  bookings.court_id    -> courts.id      ON DELETE RESTRICT  (a court with bookings can only be deactivated)
  bookings.customer_id -> customers.id   ON DELETE SET NULL
  orders.customer_id   -> customers.id   ON DELETE SET NULL
  orders.booking_id    -> bookings.id    ON DELETE SET NULL  (an order is a financial record; it outlives its booking)

Orphans are repaired first and nothing is deleted (see fk_integrity.py / scripts/check_fk_orphans.py to
preview): dangling customer/booking links become NULL; a booking whose court is gone is pointed at its
sport's only court, otherwise NULL.

PostgreSQL: plain ALTER TABLE ... ADD CONSTRAINT.
SQLite: the table is rebuilt (batch mode). The two indexes SQLAlchemy cannot reflect faithfully (the partial
unique slot index and the lower(email) expression index) are dropped and recreated by hand around the rebuild.

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
"""
import logging

import sqlalchemy as sa
from alembic import op

revision = 'o8p9q0r1s2t3'
down_revision = 'n7o8p9q0r1s2'
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

FKS = [
    # name, child table, child col, parent table, ondelete
    ("fk_bookings_court", "bookings", "court_id", "courts", "RESTRICT"),
    ("fk_bookings_customer", "bookings", "customer_id", "customers", "SET NULL"),
    ("fk_orders_customer", "orders", "customer_id", "customers", "SET NULL"),
    ("fk_orders_booking", "orders", "booking_id", "bookings", "SET NULL"),
]

SLOT_INDEX = ('CREATE UNIQUE INDEX uq_active_court_slot ON bookings(court_id, "slotId") '
              "WHERE status NOT IN ('cancelled', 'no_show')")
EMAIL_INDEX = "CREATE INDEX ix_bookings_email_lower ON bookings (lower(email))"


def _orphan_where(child: str, col: str, parent: str) -> str:
    return f'{child}."{col}" IS NOT NULL AND {child}."{col}" NOT IN (SELECT id FROM {parent})'


def _repair(bind) -> None:
    def run(sql: str) -> int:
        return bind.execute(sa.text(sql)).rowcount or 0

    where = _orphan_where("bookings", "court_id", "courts")
    remapped = run(
        'UPDATE bookings SET court_id = (SELECT c.id FROM courts c WHERE c.sport = bookings."sportSlug") '
        f'WHERE {where} AND (SELECT COUNT(*) FROM courts c WHERE c.sport = bookings."sportSlug") = 1')
    nulled = run(f"UPDATE bookings SET court_id = NULL WHERE {where}")
    if remapped or nulled:
        log.warning("FK repair: bookings.court_id remapped to the sport's court: %s, set to NULL: %s", remapped, nulled)
    for _name, child, col, parent, _od in FKS[1:]:
        n = run(f'UPDATE {child} SET "{col}" = NULL WHERE {_orphan_where(child, col, parent)}')
        if n:
            log.warning("FK repair: %s.%s dangling links set to NULL: %s", child, col, n)


def upgrade() -> None:
    bind = op.get_bind()
    _repair(bind)

    if bind.dialect.name != "sqlite":
        for name, child, col, parent, ondelete in FKS:
            op.create_foreign_key(name, child, parent, [col], ["id"], ondelete=ondelete)
        return

    op.execute("DROP INDEX IF EXISTS uq_active_court_slot")
    op.execute("DROP INDEX IF EXISTS ix_bookings_email_lower")
    for table in ("bookings", "orders"):
        with op.batch_alter_table(table, recreate="always") as b:
            for name, child, col, parent, ondelete in FKS:
                if child == table:
                    b.create_foreign_key(name, parent, [col], ["id"], ondelete=ondelete)
    op.execute(SLOT_INDEX)
    op.execute(EMAIL_INDEX)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        for name, child, _col, _parent, _od in reversed(FKS):
            op.drop_constraint(name, child, type_="foreignkey")
        return

    op.execute("DROP INDEX IF EXISTS uq_active_court_slot")
    op.execute("DROP INDEX IF EXISTS ix_bookings_email_lower")
    for table in ("orders", "bookings"):
        with op.batch_alter_table(table, recreate="always") as b:
            for name, child, *_ in reversed(FKS):
                if child == table:
                    b.drop_constraint(name, type_="foreignkey")
    op.execute(SLOT_INDEX)
    op.execute(EMAIL_INDEX)
