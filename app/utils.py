"""Pure helper functions: URL parsing, filename sanitizing, duration formatting."""
import os
import re
from pathlib import Path

# Directories a download_dir must never resolve into, even though the app
# otherwise lets the user point it anywhere they like (it's a single-user
# LAN tool with genuinely arbitrary custom folders as a supported use case).
# This blocks the concrete abuse case -- an unauthenticated LAN client
# redirecting downloads into an OS-sensitive location -- without limiting
# legitimate custom paths.
_WINDOWS_SENSITIVE_DIRS = (
    Path(os.environ.get('WINDIR', 'C:/Windows')),
    Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup',
    Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')),
)
_POSIX_SENSITIVE_DIRS = (Path('/etc'), Path('/bin'), Path('/usr'), Path('/root'), Path('/boot'), Path('/sbin'))


def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
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
    # Remove invalid filename characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove extra whitespace
    filename = ' '.join(filename.split())
    return filename


def validate_download_dir(path_str: str) -> str:
    """Reject a download_dir that would write into an OS-sensitive location.

    Raises ValueError with a user-facing reason if the path is empty, is a
    filesystem/drive root, or resolves into (or above) a known-sensitive
    directory. Returns the input unchanged (not the resolved path) so
    relative paths the user configured stay relative -- only used to
    validate, not to rewrite, the config value.
    """
    if not path_str or not path_str.strip():
        raise ValueError("download_dir cannot be empty")

    resolved = Path(path_str).expanduser().resolve()

    if resolved.anchor and resolved == Path(resolved.anchor):
        raise ValueError("download_dir cannot be a drive/filesystem root")

    sensitive_dirs = _WINDOWS_SENSITIVE_DIRS if os.name == 'nt' else _POSIX_SENSITIVE_DIRS
    for sensitive in sensitive_dirs:
        try:
            sensitive_resolved = sensitive.resolve()
        except OSError:
            continue
        if str(sensitive_resolved) and (resolved == sensitive_resolved or sensitive_resolved in resolved.parents):
            raise ValueError(f"download_dir cannot be inside {sensitive_resolved}")

    return path_str


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
