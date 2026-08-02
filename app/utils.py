"""Pure helper functions: URL parsing, filename sanitizing, duration formatting."""
import re


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
