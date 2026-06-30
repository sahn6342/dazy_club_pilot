"""
delete_test_gallery.py
----------------------
One-shot script to remove any GalleryRow whose title starts with "test"
(case-insensitive) from the live SQLite database.

Run from the apps/api directory so that the relative DB path in db.py resolves
correctly:

    cd apps/api
    python scripts/delete_test_gallery.py

The script prints how many rows it deleted and exits. It is safe to run multiple
times — a second run will simply report 0 rows deleted.
"""

import sys
import os

# Ensure the api package root is on sys.path so local imports (db, db_models) work.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from db import _session
from db_models import GalleryRow


def main() -> None:
    with _session() as s:
        result = s.execute(
            delete(GalleryRow).where(GalleryRow.title.ilike("test%"))
        )
        deleted = result.rowcount
    print(f"Deleted {deleted} gallery row(s) whose title matched 'test%'.")


if __name__ == "__main__":
    main()
