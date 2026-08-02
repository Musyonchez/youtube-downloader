"""Utility functions for JSON storage, config management, and duplicate checking."""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast


class Storage:
    """Handles all JSON file operations.

    A single process-wide lock serializes every read-modify-write sequence
    (e.g. add_to_library, remove_from_library) since the FastAPI background
    download task and API request handlers run concurrently in the same
    process and could otherwise interleave reads/writes and drop updates.
    """

    _lock = threading.Lock()

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.config_file = self.base_dir / "config.json"
        self.library_file = self.base_dir / "library.json"
        self.downloaded_file = self.base_dir / "downloaded.json"

        # Ensure files exist
        self._ensure_files()

    def _ensure_files(self):
        """Create files if they don't exist."""
        if not self.config_file.exists():
            self.save_config(self.get_default_config())
        if not self.library_file.exists():
            self._write_json(self.library_file, [])
        if not self.downloaded_file.exists():
            self._write_json(self.downloaded_file, [])

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
            return [] if file_path != self.config_file else self.get_default_config()

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
        with self._lock:
            return cast(list, self._read_json(self.library_file))

    def save_library(self, library: list[dict]):
        """Save library."""
        with self._lock:
            self._write_json(self.library_file, library)

    def add_to_library(self, item: dict):
        """Add item to library."""
        with self._lock:
            library = cast(list, self._read_json(self.library_file))
            library.append(item)
            self._write_json(self.library_file, library)

    def remove_from_library(self, video_id: str):
        """Remove item from library by video ID."""
        with self._lock:
            library = cast(list, self._read_json(self.library_file))
            library = [item for item in library if item['video_id'] != video_id]
            self._write_json(self.library_file, library)

    def clear_library(self):
        """Clear entire library."""
        with self._lock:
            self._write_json(self.library_file, [])

    # Downloaded operations
    def load_downloaded(self) -> list[dict]:
        """Load downloaded history."""
        with self._lock:
            return cast(list, self._read_json(self.downloaded_file))

    def save_downloaded(self, downloaded: list[dict]):
        """Save downloaded history."""
        with self._lock:
            self._write_json(self.downloaded_file, downloaded)

    def add_to_downloaded(self, item: dict):
        """Add item to downloaded history (permanent record)."""
        item = {**item, 'downloaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with self._lock:
            downloaded = cast(list, self._read_json(self.downloaded_file))
            downloaded.append(item)
            self._write_json(self.downloaded_file, downloaded)

    # Duplicate checking
    def is_downloaded(self, video_id: str) -> bool:
        """Check if video has been downloaded."""
        downloaded = self.load_downloaded()
        return any(item['video_id'] == video_id for item in downloaded)

    def is_in_library(self, video_id: str) -> bool:
        """Check if video is in library queue."""
        library = self.load_library()
        return any(item['video_id'] == video_id for item in library)

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
