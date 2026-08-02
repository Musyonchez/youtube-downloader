"""SQLite-backed storage for the library queue and download history.

Replaces the previous flat-JSON approach for these two datasets: every
load_library()/load_downloaded() call used to read and parse the *entire*
file, and duplicate checks (is_downloaded, is_in_library) did a full O(n)
scan over it. With 655+ history entries and growing, that's an increasing
amount of work for every single API request. SQLite gives indexed
primary-key lookups instead, and only touches the rows actually read or
written.

config.json is intentionally left as-is -- it's a single small object with
no growth and no query needs, so a database would be pure overhead there.
"""
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    channel TEXT NOT NULL,
    duration TEXT NOT NULL,
    url TEXT NOT NULL,
    thumbnail TEXT NOT NULL,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downloaded (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    channel TEXT NOT NULL,
    duration TEXT NOT NULL,
    url TEXT NOT NULL,
    thumbnail TEXT NOT NULL,
    success INTEGER NOT NULL,
    file_path TEXT,
    downloaded_at TEXT NOT NULL
);
"""


class Database:
    """Thin, explicit wrapper around the two tables this app needs.

    Deliberately not a generic dict-to-SQL layer: two tables with fixed,
    known columns is simpler and safer (no dynamically built column lists)
    than a small ORM for what's still a very small app.
    """

    _lock = threading.Lock()

    def __init__(self, db_path: str = "downloads.db"):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # Library operations
    def get_library(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM library ORDER BY added_at").fetchall()
            return [dict(row) for row in rows]

    def add_library_item(self, item: dict, added_at: str):
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO library
                   (video_id, title, channel, duration, url, thumbnail, added_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (item['video_id'], item['title'], item['channel'], item['duration'],
                 item['url'], item['thumbnail'], added_at),
            )
            self._conn.commit()

    def remove_library_item(self, video_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM library WHERE video_id = ?", (video_id,))
            self._conn.commit()

    def clear_library(self):
        with self._lock:
            self._conn.execute("DELETE FROM library")
            self._conn.commit()

    def is_in_library(self, video_id: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM library WHERE video_id = ?", (video_id,)).fetchone()
            return row is not None

    # Downloaded operations
    def get_downloaded(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM downloaded ORDER BY downloaded_at").fetchall()
            results = [dict(row) for row in rows]
            for result in results:
                result['success'] = bool(result['success'])
            return results

    def add_downloaded_item(self, item: dict, downloaded_at: str):
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO downloaded
                   (video_id, title, channel, duration, url, thumbnail, success, file_path, downloaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item['video_id'], item['title'], item['channel'], item['duration'], item['url'],
                 item['thumbnail'], 1 if item.get('success') else 0, item.get('file_path'), downloaded_at),
            )
            self._conn.commit()

    def is_downloaded(self, video_id: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM downloaded WHERE video_id = ?", (video_id,)).fetchone()
            return row is not None

    def count_library(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM library").fetchone()
            return int(row['n'])

    def count_downloaded(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM downloaded").fetchone()
            return int(row['n'])
