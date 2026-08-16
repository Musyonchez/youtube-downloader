"""Pure helper functions: URL parsing, filename sanitizing, duration formatting."""
import os
import re
from pathlib import Path

# Directories a download_dir must never resolve into, even though the app
# otherwise lets the user point it anywhere they like (it's a single-account
# tool with genuinely arbitrary custom folders as a supported use case).
# This blocks the concrete abuse case -- the logged-in account (or, before
# docs/15's session auth, any LAN client at all) redirecting downloads into
# an OS-sensitive location -- without limiting legitimate custom paths.
_WINDOWS_SENSITIVE_DIRS = (
    Path(os.environ.get('WINDIR', 'C:/Windows')),
    Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup',
    Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')),
)
_POSIX_SENSITIVE_DIRS = (Path('/etc'), Path('/bin'), Path('/usr'), Path('/root'), Path('/boot'), Path('/sbin'))

# Windows reserves these stems (case-insensitive, extension doesn't save you --
# "NUL.mp3" is just as reserved as "NUL") for device files.
_WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}
# Leaves headroom under Windows' ~260-char path limit for the download_dir
# prefix and the .mp3 suffix -- long enough that truncation is rare, short
# enough that it can't blow the limit on its own.
_MAX_FILENAME_STEM_LENGTH = 150


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
    """Remove invalid characters from filename, and guard against a few
    Windows-specific edge cases that a title full of punctuation can hit:
    a name that sanitizes to nothing, a name that collides with a reserved
    device name (NUL, CON, COM1, ...), or one long enough to blow past the
    filesystem path limit once combined with a download directory."""
    # Remove invalid filename characters, plus control characters (including
    # embedded nulls) that the original punctuation-only regex let through.
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    # Remove extra whitespace
    filename = ' '.join(filename.split())

    if not filename:
        filename = 'untitled'

    if filename.upper() in _WINDOWS_RESERVED_NAMES:
        filename = f'_{filename}'

    if len(filename) > _MAX_FILENAME_STEM_LENGTH:
        filename = filename[:_MAX_FILENAME_STEM_LENGTH].rstrip()

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
