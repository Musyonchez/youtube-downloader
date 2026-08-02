"""YouTube downloader with progress tracking and metadata tagging."""
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from app.utils import sanitize_filename

console = Console()
logger = logging.getLogger(__name__)

# Called with (video_id, percent) as each video downloads, e.g. to broadcast over a WebSocket.
ProgressCallback = Callable[[str, float], None]


class YouTubeDownloader:
    """Handles downloading YouTube videos as MP3 files."""

    def __init__(
        self,
        download_dir: str = "./downloads",
        audio_quality: str = "320",
        progress_callback: ProgressCallback | None = None,
    ):
        self.download_dir = Path(download_dir)
        self.audio_quality = audio_quality
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback

        # Progress tracking
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self._current_video_id: str | None = None

    def _progress_hook(self, d):
        """Progress callback for yt-dlp."""
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)

            if total > 0:
                if self.task_id is not None and self.progress is not None:
                    self.progress.update(self.task_id, completed=downloaded, total=total)

                if self.progress_callback is not None and self._current_video_id is not None:
                    self.progress_callback(self._current_video_id, round(downloaded / total * 100, 1))

        elif d['status'] == 'finished':
            if self.task_id is not None and self.progress is not None:
                self.progress.update(self.task_id, completed=100, total=100)

            if self.progress_callback is not None and self._current_video_id is not None:
                self.progress_callback(self._current_video_id, 100.0)

    def download_audio(self, video_info: dict) -> str | None:
        """Download video as MP3 audio file."""
        base_name = None
        try:
            url = video_info['url']
            title = video_info['title']
            channel = video_info['channel']
            self._current_video_id = video_info.get('video_id')

            if shutil.which('ffmpeg') is None:
                console.print(
                    "[red]✗ FFmpeg not found on PATH -- required to convert downloads to MP3. "
                    "Install it (e.g. `winget install Gyan.FFmpeg` on Windows, "
                    "`sudo apt install ffmpeg` on Debian/Ubuntu) and restart the app.[/red]"
                )
                logger.error("FFmpeg not found; cannot download %s", title)
                return None

            # Create filename: "Artist - Title.mp3"
            base_name = sanitize_filename(f"{channel} - {title}")
            filename = f"{base_name}.mp3"
            output_path = self.download_dir / filename

            # Check if file already exists
            if output_path.exists():
                console.print(f"[yellow]File already exists: {filename}[/yellow]")
                return str(output_path)

            console.print(f"[cyan]Downloading: {title}[/cyan]")

            # yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': self.audio_quality,
                }],
                # %(ext)s is required: without it yt-dlp writes the raw
                # download (webm/m4a/opus, before FFmpeg conversion) to this
                # exact literal path with no extension at all -- which is
                # exactly what was left behind if FFmpeg conversion failed.
                'outtmpl': str(self.download_dir / base_name) + '.%(ext)s',
                'progress_hooks': [self._progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            # Download with progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                self.progress = progress
                self.task_id = progress.add_task(f"Downloading {title[:40]}...", total=100)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                self.progress = None
                self.task_id = None

            # Tag the MP3 file
            self._tag_mp3(output_path, video_info)

            console.print(f"[green]✓ Downloaded: {filename}[/green]")
            return str(output_path)

        except Exception as e:
            console.print(f"[red]✗ Error downloading {video_info['title']}: {str(e)}[/red]")
            logger.exception("Failed to download %s (%s)", video_info.get('title'), video_info.get('video_id'))
            if base_name:
                self._cleanup_partial_download(base_name)
            return None

    def _cleanup_partial_download(self, base_name: str):
        """Remove any raw/partial file yt-dlp wrote before a failure (e.g. the
        FFmpeg conversion step failing) instead of leaving it behind under a
        filename that looks like -- but isn't -- the expected MP3."""
        for leftover in self.download_dir.glob(f"{base_name}.*"):
            try:
                leftover.unlink()
                logger.info("Removed orphaned partial download: %s", leftover)
            except OSError:
                logger.warning("Could not remove orphaned partial download: %s", leftover)

    def _tag_mp3(self, file_path: Path, video_info: dict):
        """Add metadata tags to MP3 file."""
        try:
            # Try to load existing tags
            try:
                audio = EasyID3(file_path)
            except ID3NoHeaderError:
                # Create new ID3 tag if none exists
                mp3 = MP3(file_path)
                mp3.add_tags()
                mp3.save()
                audio = EasyID3(file_path)

            # Set tags
            audio['title'] = video_info['title']
            audio['artist'] = video_info['channel']
            audio['album'] = 'YouTube Downloads'

            audio.save()

        except Exception as e:
            console.print(f"[yellow]Warning: Could not tag file: {str(e)}[/yellow]")

    def download_batch(self, video_list: list[dict]) -> list[dict]:
        """Download multiple videos and return results."""
        results = []

        console.print(f"\n[bold cyan]Starting batch download of {len(video_list)} items...[/bold cyan]\n")

        for i, video_info in enumerate(video_list, 1):
            console.print(f"[bold]({i}/{len(video_list)})[/bold]")

            file_path = self.download_audio(video_info)

            result = {
                **video_info,
                'success': file_path is not None,
                'file_path': file_path
            }
            results.append(result)

            console.print()  # Add blank line between downloads

        # Summary
        success_count = sum(1 for r in results if r['success'])
        console.print(f"\n[bold green]✓ Successfully downloaded: {success_count}/{len(video_list)}[/bold green]")

        if success_count < len(video_list):
            failed_count = len(video_list) - success_count
            console.print(f"[bold red]✗ Failed: {failed_count}[/bold red]")

        return results


def test_download():
    """Test function for download functionality."""
    downloader = YouTubeDownloader()

    test_video = {
        'video_id': 'jfKfPfyJRdk',
        'title': 'lofi hip hop radio',
        'channel': 'Lofi Girl',
        'duration': '00:00',
        'url': 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
    }

    print("Testing download...")
    result = downloader.download_audio(test_video)
    print(f"Download result: {result}")


if __name__ == "__main__":
    test_download()
