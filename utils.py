"""Storage: JSON for config, SQLite for the library queue and download history."""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from db import Database


class Storage:
    """Config lives in config.json (small, rarely written, no query needs).
    Library queue and download history live in SQLite via db.Database --
    see db.py for why.
    """

    _lock = threading.Lock()

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
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
    def load_downloaded(self) -> list[dict]:
        """Load downloaded history."""
        return self.db.get_downloaded()

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


def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
    import re

    # Handle various YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*?v=([^&\n?#]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # If it's already just an ID
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    return None


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename."""
    import re
    # Remove invalid filename characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove extra whitespace
    filename = ' '.join(filename.split())
    return filename


def format_duration(seconds) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    if seconds is None or seconds == 0:
        return "00:00"

    # Convert to int to handle float values from yt-dlp
    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
