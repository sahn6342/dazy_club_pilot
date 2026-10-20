"""
check_fk_orphans.py
-------------------
Dry-run (read-only) report of rows whose "soft" foreign keys point at nothing:

    bookings.court_id    -> courts.id
    bookings.customer_id -> customers.id
    orders.customer_id   -> customers.id
    orders.booking_id    -> bookings.id

Run this against the real database BEFORE deploying the migration that turns these into real
foreign keys (n7o8p9q0r1s2 -> o8p9q0r1s2t3). The migration repairs orphans itself, but you should
see what it will touch first:

    cd apps/api
    uv run python scripts/check_fk_orphans.py            # report only; exit 1 if anything is orphaned
    uv run python scripts/check_fk_orphans.py --repair   # apply the same repair the migration does

It reads DAZY_DB_URL (or the local SQLite file) exactly like the API. For Neon, export the pooled
URL of the production branch (or, safer, of a branch copy) first. Nothing is ever deleted: dangling
customer/booking links become NULL, and a booking whose court is gone is pointed at its sport's only
court (or NULL when that sport has several).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import DB_URL, engine  # noqa: E402
from fk_integrity import find_orphans, repair  # noqa: E402


def _redacted(url: str) -> str:
    if "@" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repair", action="store_true", help="fix orphans (same rules as the migration); default is report only")
    args = ap.parse_args()

    print(f"Database: {_redacted(DB_URL)}")
    with engine.begin() as conn:
        reports = find_orphans(conn)
        total = sum(r.count for r in reports)
        for r in reports:
            flag = "OK " if r.count == 0 else "!! "
            print(f"{flag}{r.relation.label}: {r.count} orphan row(s)")
            for rid, val in zip(r.sample_ids, r.sample_values):
                print(f"      row {rid} -> missing {r.relation.parent} id {val}")
        if total == 0:
            print("\nNo orphans: the foreign-key migration will add the constraints without touching any row.")
            return 0
        if not args.repair:
            print(f"\n{total} orphan row(s). Nothing was changed. Re-run with --repair to fix them "
                  "(the migration does the same automatically).")
            return 1
        for label, n in repair(conn).items():
            print(f"repaired {label}: {n} row(s)")
        left = sum(r.count for r in find_orphans(conn))
        print(f"\nOrphans remaining: {left}")
        return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
