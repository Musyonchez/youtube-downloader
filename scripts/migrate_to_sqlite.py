"""One-time migration: import library.json/downloaded.json into downloads.db.

Run manually once: `python scripts/migrate_to_sqlite.py`. Safe to re-run --
uses INSERT OR REPLACE keyed on video_id, so re-running just re-imports the
same rows. Does not delete or modify the source JSON files.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.storage.db import Database  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def migrate():
    db = Database(str(ROOT / "data" / "downloads.db"))

    library_file = ROOT / "library.json"
    if library_file.exists():
        library = json.loads(library_file.read_text(encoding='utf-8'))
        for item in library:
            db.add_library_item(item, added_at=item.get('added_at', ''))
        print(f"Imported {len(library)} library item(s)")

    downloaded_file = ROOT / "downloaded.json"
    if downloaded_file.exists():
        downloaded = json.loads(downloaded_file.read_text(encoding='utf-8'))
        for item in downloaded:
            db.add_downloaded_item(item, downloaded_at=item.get('downloaded_at', ''))
        print(f"Imported {len(downloaded)} downloaded item(s)")

    print(f"Done. downloads.db now has {db.count_library()} library item(s) "
          f"and {db.count_downloaded()} downloaded item(s).")


if __name__ == "__main__":
    migrate()
