"""Utility functions for JSON storage, config management, and duplicate checking."""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class Storage:
    """Handles all JSON file operations."""

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
    def get_default_config() -> Dict:
        """Return default configuration."""
        return {
            "audio_quality": "320",
            "format": "mp3",
            "download_dir": "./downloads",
            "last_updated": datetime.now().strftime("%Y-%m-%d")
        }

    def _read_json(self, file_path: Path) -> any:
        """Read and parse JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return [] if file_path != self.config_file else self.get_default_config()

    def _write_json(self, file_path: Path, data: any):
        """Write data to JSON file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Config operations
    def load_config(self) -> Dict:
        """Load configuration."""
        return self._read_json(self.config_file)

    def save_config(self, config: Dict):
        """Save configuration."""
        config['last_updated'] = datetime.now().strftime("%Y-%m-%d")
        self._write_json(self.config_file, config)

    def update_config(self, **kwargs):
        """Update specific config values."""
        config = self.load_config()
        config.update(kwargs)
        self.save_config(config)

    # Library operations
    def load_library(self) -> List[Dict]:
        """Load library (queue to download)."""
        return self._read_json(self.library_file)

    def save_library(self, library: List[Dict]):
        """Save library."""
        self._write_json(self.library_file, library)

    def add_to_library(self, item: Dict):
        """Add item to library."""
        library = self.load_library()
        library.append(item)
        self.save_library(library)

    def remove_from_library(self, video_id: str):
        """Remove item from library by video ID."""
        library = self.load_library()
        library = [item for item in library if item['video_id'] != video_id]
        self.save_library(library)

    def clear_library(self):
        """Clear entire library."""
        self.save_library([])

    # Downloaded operations
    def load_downloaded(self) -> List[Dict]:
        """Load downloaded history."""
        return self._read_json(self.downloaded_file)

    def save_downloaded(self, downloaded: List[Dict]):
        """Save downloaded history."""
        self._write_json(self.downloaded_file, downloaded)

    def add_to_downloaded(self, item: Dict):
        """Add item to downloaded history (permanent record)."""
        downloaded = self.load_downloaded()
        # Add download timestamp
        item['downloaded_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        downloaded.append(item)
        self.save_downloaded(downloaded)

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


def extract_video_id(url: str) -> Optional[str]:
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


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
