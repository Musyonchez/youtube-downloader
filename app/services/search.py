"""YouTube search and video information retrieval."""
import yt_dlp
from rich.console import Console

from app.utils import extract_video_id, format_duration

console = Console()


class YouTubeSearcher:
    """Handles YouTube search and metadata extraction."""

    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

    def search_by_name(self, query: str, limit: int = 10) -> list[dict]:
        """Search YouTube by name and return results using yt-dlp."""
        try:
            console.print(f"[cyan]Searching for: {query}...[/cyan]")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Use yt-dlp's search functionality
                search_query = f"ytsearch{limit}:{query}"
                info = ydl.extract_info(search_query, download=False)

                if info is None or 'entries' not in info:
                    return []

                formatted_results = []
                for video in info['entries']:
                    if video is None:
                        continue

                    video_id = video.get('id', '')
                    # Construct YouTube thumbnail URL from video ID
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg" if video_id else ''

                    formatted_results.append({
                        'video_id': video_id,
                        'title': video.get('title', 'Unknown'),
                        'channel': video.get('uploader', video.get('channel', 'Unknown')),
                        'duration': format_duration(video.get('duration', 0)),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'thumbnail': thumbnail_url
                    })

                return formatted_results

        except Exception as e:
            console.print(f"[red]Error searching: {str(e)}[/red]")
            return []

    def get_video_info(self, url: str) -> dict | None:
        """Get video information from URL."""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    return None

                # Extract relevant information
                video_id = extract_video_id(url) or info.get('id', '')
                # Use YouTube thumbnail URL or fall back to info thumbnail
                thumbnail_url = info.get('thumbnail', '') or f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

                return {
                    'video_id': video_id,
                    'title': info.get('title', 'Unknown'),
                    'channel': info.get('uploader', 'Unknown'),
                    'duration': format_duration(info.get('duration', 0)),
                    'url': url if 'youtube.com' in url or 'youtu.be' in url else f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail': thumbnail_url
                }

        except Exception as e:
            console.print(f"[red]Error getting video info: {str(e)}[/red]")
            return None

    def get_playlist_videos(self, playlist_url: str) -> list[dict]:
        """Get all videos from a playlist URL."""
        try:
            console.print("[cyan]Fetching playlist information...[/cyan]")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlist_items': '1-1000',  # Limit to first 1000 videos
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)

                if info is None or 'entries' not in info:
                    console.print("[red]Could not fetch playlist or playlist is empty[/red]")
                    return []

                videos = []
                entries = info.get('entries', [])

                console.print(f"[cyan]Found {len(entries)} videos in playlist[/cyan]")

                for entry in entries:
                    if entry is None:
                        continue

                    video_id = entry.get('id', '')
                    if not video_id:
                        continue

                    # Construct YouTube thumbnail URL
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

                    videos.append({
                        'video_id': video_id,
                        'title': entry.get('title', 'Unknown'),
                        'channel': entry.get('uploader', info.get('uploader', 'Unknown')),
                        'duration': format_duration(entry.get('duration', 0)),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'thumbnail': thumbnail_url
                    })

                return videos

        except Exception as e:
            console.print(f"[red]Error fetching playlist: {str(e)}[/red]")
            return []

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate if URL is a valid YouTube URL and return type."""
        # Check if it's a playlist, mix, or radio (has list= parameter)
        if 'list=' in url:
            return True, 'playlist'
        elif 'youtube.com' in url or 'youtu.be' in url:
            return True, 'video'
        else:
            return False, 'invalid'


def test_search():
    """Test function for search functionality."""
    searcher = YouTubeSearcher()

    # Test search by name
    print("\n=== Testing Search by Name ===")
    results = searcher.search_by_name("lofi hip hop", limit=5)
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} - {result['channel']} ({result['duration']})")

    # Test get video info
    print("\n=== Testing Get Video Info ===")
    video_info = searcher.get_video_info("https://www.youtube.com/watch?v=jfKfPfyJRdk")
    if video_info:
        print(f"Title: {video_info['title']}")
        print(f"Channel: {video_info['channel']}")
        print(f"Duration: {video_info['duration']}")


if __name__ == "__main__":
    test_search()
