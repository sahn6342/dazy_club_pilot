"""
reset_demo_content.py
----------------------
One-shot script to remove seeded demo content from a LIVE database before
launch (Detailed-Roadmap.md Phase 1). Targets exactly the rows inserted by
seed.py's GALLERY_ITEMS/TESTIMONIALS ids and the WELCOME10/FLAT100 promo
codes - never touches venues/courts/schedule/bookings.

After running, add real gallery photos, testimonials, and promo codes via
the admin app (Gallery / Testimonials / Promos pages) - this script only
clears the placeholders.

Dry-run by default; pass --yes to actually delete.

Run inside the api container (env vars already point at the production DB):

    docker compose exec api python scripts/reset_demo_content.py --yes

Or locally from the apps/api directory:

    cd apps/api
    python scripts/reset_demo_content.py --yes

Safe to run multiple times - a second run reports 0 rows for whatever
was already removed.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from db import _session
from db_models import GalleryRow, TestimonialRow, PromoCodeRow

_SEEDED_GALLERY_IDS = ["gallery-1", "gallery-2", "gallery-3"]
_SEEDED_TESTIMONIAL_IDS = ["testimonial-1", "testimonial-2"]
_SEEDED_PROMO_CODES = ["WELCOME10", "FLAT100"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="actually delete (default: dry-run report only)")
    args = parser.parse_args()

    with _session() as s:
        gallery = s.scalars(select(GalleryRow).where(GalleryRow.id.in_(_SEEDED_GALLERY_IDS))).all()
        testimonials = s.scalars(select(TestimonialRow).where(TestimonialRow.id.in_(_SEEDED_TESTIMONIAL_IDS))).all()
        promos = s.scalars(select(PromoCodeRow).where(PromoCodeRow.code.in_(_SEEDED_PROMO_CODES))).all()

        print(f"Seeded gallery items found:     {len(gallery)}  {[g.title for g in gallery]}")
        print(f"Seeded testimonials found:      {len(testimonials)}  {[t.name for t in testimonials]}")
        print(f"Seeded promo codes found:       {len(promos)}  {[p.code for p in promos]}")

        if not args.yes:
            print("\nDry run - no changes made. Re-run with --yes to delete the above.")
            return

        s.execute(delete(GalleryRow).where(GalleryRow.id.in_(_SEEDED_GALLERY_IDS)))
        s.execute(delete(TestimonialRow).where(TestimonialRow.id.in_(_SEEDED_TESTIMONIAL_IDS)))
        s.execute(delete(PromoCodeRow).where(PromoCodeRow.code.in_(_SEEDED_PROMO_CODES)))

    print("\nDeleted. Add real gallery photos, testimonials, and promo codes via the admin app.")


if __name__ == "__main__":
    main()
