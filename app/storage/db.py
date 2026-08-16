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

-- Single-account auth (docs/15). username is the primary key rather than
-- an auto-increment id -- there's no other table that references a user
-- by foreign key, and "first user, then registration closes" means this
-- table only ever holds one row in practice.
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
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
    def get_downloaded(self, limit: int | None = None, offset: int = 0, descending: bool = False) -> list[dict]:
        """Return download-history rows, oldest first by default
        (`descending=True` for newest first -- what the /history page
        wants, so its "load more" can page from the newest end with a
        plain OFFSET instead of fetching everything and reversing it).

        `limit`/`offset` bound how much comes back in one call -- with the
        table only growing (every attempt, success or failure, is kept
        forever) and no cap, a plain `SELECT *` here means every page load
        pulls the *entire* history into memory and over the wire, getting
        slower release over release. `limit=None` (the default) keeps the
        old unbounded behavior for callers that genuinely need everything
        (e.g. tests, scripts) -- app/api/routes.py's /api/downloaded route
        always passes an explicit bounded limit.
        """
        with self._lock:
            order = "DESC" if descending else "ASC"
            query = f"SELECT * FROM downloaded ORDER BY downloaded_at {order}"
            params: tuple = ()
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params = (limit, offset)
            rows = self._conn.execute(query, params).fetchall()
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
        """True only for a *successful* download -- a failed attempt leaves a row
        (so its history isn't lost) but must not block the video from being
        re-queued, so this checks success=1 rather than mere row presence."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM downloaded WHERE video_id = ? AND success = 1", (video_id,)
            ).fetchone()
            return row is not None

    def get_statuses(self, video_ids: list[str]) -> dict[str, str]:
        """Batch status lookup: 'downloaded' | 'queued' | 'new' per video_id.

        Replaces calling is_downloaded()/is_in_library() once per item (each its
        own locked round-trip) with two IN-queries total, regardless of how many
        ids are passed -- matters for playlists, which can be up to 1000 items.
        """
        if not video_ids:
            return {}
        with self._lock:
            placeholders = ','.join('?' * len(video_ids))
            downloaded_ids = {
                row['video_id'] for row in self._conn.execute(
                    f"SELECT video_id FROM downloaded WHERE success = 1 AND video_id IN ({placeholders})",
                    video_ids,
                ).fetchall()
            }
            library_ids = {
                row['video_id'] for row in self._conn.execute(
                    f"SELECT video_id FROM library WHERE video_id IN ({placeholders})", video_ids
                ).fetchall()
            }
        statuses = {}
        for vid in video_ids:
            if vid in downloaded_ids:
                statuses[vid] = 'downloaded'
            elif vid in library_ids:
                statuses[vid] = 'queued'
            else:
                statuses[vid] = 'new'
        return statuses

    def count_library(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM library").fetchone()
            return int(row['n'])

    def count_downloaded(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM downloaded").fetchone()
            return int(row['n'])

    # User operations (docs/15 -- single-account session auth)
    def create_user(self, username: str, password_hash: str, created_at: str):
        """Insert a new user. Deliberately plain INSERT (not INSERT OR
        REPLACE like library/downloaded use) -- a duplicate username must
        fail loudly (sqlite3.IntegrityError) rather than silently
        overwrite an existing account's password hash. Callers are
        expected to gate on count_users() == 0 first (the actual security
        boundary); this constraint is the last-resort backstop."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, created_at),
            )
            self._conn.commit()

    def create_user_if_first(self, username: str, password_hash: str, created_at: str) -> bool:
        """Atomically create `username` as the account, but only if the
        users table is still empty. Returns True if the account was
        created, False if it wasn't (someone already registered).

        This is the real fix for the registration race (docs/16, 16-1):
        a plain "count_users() == 0, then create_user()" from the caller
        is *two* separate lock acquisitions, so two concurrent requests
        with two *different* usernames can each see count == 0 before
        either commits, and both end up creating an account -- the
        UNIQUE constraint on `username` only rejects a collision on the
        same name, not a second, different account. Doing the count
        check and the insert under one `_lock` acquisition here closes
        that window: only the first caller to hold the lock while the
        table is still empty gets to insert.
        """
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            if int(row['n']) > 0:
                return False
            self._conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, created_at),
            )
            self._conn.commit()
            return True

    def get_user(self, username: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row is not None else None

    def count_users(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            return int(row['n'])
