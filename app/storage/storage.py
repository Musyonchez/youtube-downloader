"""Storage facade: JSON for config, SQLite for the library queue and download history."""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from app.storage.db import Database


class Storage:
    """Config lives in config.json (small, rarely written, no query needs).
    Library queue and download history live in SQLite via db.Database --
    see db.py for why.
    """

    _lock = threading.Lock()

    def __init__(self, base_dir: str | None = None):
        # `base_dir` is only ever left at its default in production
        # (app/api/routes.py's module-level `storage = Storage()`) --
        # every test passes an explicit tmp_path. That default used to be
        # the bare relative string "data", coupled to persistent storage
        # only *implicitly*: it happens to land on the Fly volume mount
        # because the Dockerfile's WORKDIR and fly.toml's mount destination
        # both happen to agree on /srv/data, with nothing actually
        # enforcing that agreement (docs/16, 16-21) -- a future change to
        # either one could silently make this resolve to the container's
        # ephemeral filesystem instead, losing the account/library/history
        # on every restart with no error. DATA_DIR makes the coupling
        # explicit: unset, it still defaults to "data" (unchanged local-dev
        # behavior); fly.toml now sets it to the mount path directly.
        self.base_dir = Path(base_dir if base_dir is not None else os.environ.get("DATA_DIR", "data"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.base_dir / "config.json"
        self.db = Database(str(self.base_dir / "downloads.db"))

        if not self.config_file.exists():
            self.save_config(self.get_default_config())

    @staticmethod
    def get_default_config() -> dict:
        """Return default configuration."""
        return {
            "audio_quality": "320",
            "format": "mp3",
            "download_dir": "./downloads",
            "last_updated": datetime.now().strftime("%Y-%m-%d")
        }

    def _read_json(self, file_path: Path) -> Any:
        """Read and parse JSON file."""
        try:
            with open(file_path, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return self.get_default_config()

    def _write_json(self, file_path: Path, data: Any):
        """Write data to JSON file atomically (write to temp file, then rename)."""
        tmp_path = file_path.with_suffix(f'{file_path.suffix}.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, file_path)

    # Config operations
    def load_config(self) -> dict:
        """Load configuration."""
        with self._lock:
            return cast(dict, self._read_json(self.config_file))

    def save_config(self, config: dict):
        """Save configuration."""
        config['last_updated'] = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            self._write_json(self.config_file, config)

    def update_config(self, **kwargs):
        """Update specific config values."""
        with self._lock:
            config = cast(dict, self._read_json(self.config_file))
            config.update(kwargs)
            config['last_updated'] = datetime.now().strftime("%Y-%m-%d")
            self._write_json(self.config_file, config)

    # Library operations
    def load_library(self) -> list[dict]:
        """Load library (queue to download)."""
        return self.db.get_library()

    def add_to_library(self, item: dict):
        """Add item to library."""
        self.db.add_library_item(item, added_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def remove_from_library(self, video_id: str):
        """Remove item from library by video ID."""
        self.db.remove_library_item(video_id)

    def clear_library(self):
        """Clear entire library."""
        self.db.clear_library()

    def count_library(self) -> int:
        """Number of items in the library queue."""
        return self.db.count_library()

    # Downloaded operations
    def load_downloaded(self, limit: int | None = None, offset: int = 0, descending: bool = False) -> list[dict]:
        """Load downloaded history. `limit`/`offset` page through it
        instead of loading the whole (ever-growing) table -- see
        db.Database.get_downloaded's docstring (docs/16, 16-8)."""
        return self.db.get_downloaded(limit=limit, offset=offset, descending=descending)

    def count_downloaded(self) -> int:
        """Number of items in download history."""
        return self.db.count_downloaded()

    def add_to_downloaded(self, item: dict):
        """Add item to downloaded history (permanent record)."""
        self.db.add_downloaded_item(item, downloaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Duplicate checking
    def is_downloaded(self, video_id: str) -> bool:
        """Check if video has been downloaded."""
        return self.db.is_downloaded(video_id)

    def is_in_library(self, video_id: str) -> bool:
        """Check if video is in library queue."""
        return self.db.is_in_library(video_id)

    def get_item_status(self, video_id: str) -> str:
        """Get status of video: 'downloaded', 'queued', or 'new'."""
        if self.is_downloaded(video_id):
            return 'downloaded'
        elif self.is_in_library(video_id):
            return 'queued'
        else:
            return 'new'

    def get_statuses(self, video_ids: list[str]) -> dict[str, str]:
        """Batch version of get_item_status -- two queries total instead of
        up to 2 per id. Use this for search/playlist results (dozens to
        hundreds of items) instead of looping get_item_status()."""
        return self.db.get_statuses(video_ids)

    # User operations (docs/15)
    def create_user(self, username: str, password_hash: str):
        """Create a new user account. Raises sqlite3.IntegrityError if the
        username already exists -- see db.create_user's docstring."""
        self.db.create_user(username, password_hash, created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def create_user_if_first(self, username: str, password_hash: str) -> bool:
        """Atomically create `username` as the sole account, only if no
        account exists yet. Returns False (does nothing) if one already
        does -- this is the actual registration-race fix (docs/16, 16-1),
        see db.create_user_if_first's docstring."""
        return self.db.create_user_if_first(
            username, password_hash, created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def get_user(self, username: str) -> dict | None:
        """Look up a user by username, or None if it doesn't exist."""
        return self.db.get_user(username)

    def count_users(self) -> int:
        """Number of registered accounts -- drives the registration gate
        (registration is only open while this is 0)."""
        return self.db.count_users()
