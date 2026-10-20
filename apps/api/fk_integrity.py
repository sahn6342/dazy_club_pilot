"""Referential-integrity audit for the relationships that used to be "soft" foreign keys.

Used by scripts/check_fk_orphans.py (run it against production BEFORE deploying the migration that
adds the constraints) and by the tests. The migration itself carries its own copy of the repair SQL
so it never depends on application code that may change later."""
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class Relation:
    label: str          # "bookings.court_id -> courts.id"
    child: str
    column: str
    parent: str
    on_orphan: str      # what the migration/--repair does: "null" or "remap_court"


RELATIONS = [
    Relation("bookings.court_id -> courts.id", "bookings", "court_id", "courts", "remap_court"),
    Relation("bookings.customer_id -> customers.id", "bookings", "customer_id", "customers", "null"),
    Relation("orders.customer_id -> customers.id", "orders", "customer_id", "customers", "null"),
    Relation("orders.booking_id -> bookings.id", "orders", "booking_id", "bookings", "null"),
]


@dataclass
class OrphanReport:
    relation: Relation
    count: int
    sample_ids: list[str] = field(default_factory=list)
    sample_values: list[str] = field(default_factory=list)  # the dangling parent ids


def _where(rel: Relation) -> str:
    return (f'{rel.child}."{rel.column}" IS NOT NULL AND {rel.child}."{rel.column}" NOT IN '
            f'(SELECT id FROM {rel.parent})')


def find_orphans(conn: Connection, sample: int = 5) -> list[OrphanReport]:
    """Child rows whose parent id points at nothing. Read-only."""
    out = []
    for rel in RELATIONS:
        where = _where(rel)
        count = conn.execute(text(f"SELECT COUNT(*) FROM {rel.child} WHERE {where}")).scalar() or 0
        ids, vals = [], []
        if count:
            for row in conn.execute(text(f'SELECT id, "{rel.column}" FROM {rel.child} WHERE {where} ORDER BY id LIMIT {int(sample)}')):
                ids.append(str(row[0]))
                vals.append(str(row[1]))
        out.append(OrphanReport(rel, count, ids, vals))
    return out


def repair(conn: Connection) -> dict[str, int]:
    """Make every orphan consistent without deleting any row:
      * dangling customer/booking links become NULL;
      * a booking whose court is gone is pointed at its sport's court when that sport has exactly one,
        otherwise the link becomes NULL (the booking stays; an admin can see it needs a court).
    Returns {label: rows changed}. The caller owns the transaction."""
    changed: dict[str, int] = {}
    for rel in RELATIONS:
        where = _where(rel)
        n = 0
        if rel.on_orphan == "remap_court":
            n += conn.execute(text(
                f'UPDATE bookings SET court_id = (SELECT c.id FROM courts c WHERE c.sport = bookings."sportSlug") '
                f'WHERE {where} AND (SELECT COUNT(*) FROM courts c WHERE c.sport = bookings."sportSlug") = 1'
            )).rowcount or 0
        n += conn.execute(text(f'UPDATE {rel.child} SET "{rel.column}" = NULL WHERE {where}')).rowcount or 0
        changed[rel.label] = n
    return changed
