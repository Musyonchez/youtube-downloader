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


def _safe_print(msg: str):
    """console.print(), but never let a console-encoding failure (e.g. the
    Windows cp1252 console choking on an emoji glyph) propagate and be
    mistaken for a real download failure -- it previously could land in
    download_audio's except block and skip orphan-file cleanup, or even
    delete an already-finished file (see docs/09, AUD-04)."""
    try:
        console.print(msg)
    except Exception:
        logger.debug("console.print failed (non-fatal): %r", msg)


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
        output_path = None
        try:
            url = video_info['url']
            title = video_info['title']
            channel = video_info['channel']
            self._current_video_id = video_info.get('video_id')

            if shutil.which('ffmpeg') is None:
                logger.error("FFmpeg not found; cannot download %s", title)
                _safe_print(
                    "[red]✗ FFmpeg not found on PATH -- required to convert downloads to MP3. "
                    "Install it (e.g. `winget install Gyan.FFmpeg` on Windows, "
                    "`sudo apt install ffmpeg` on Debian/Ubuntu) and restart the app.[/red]"
                )
                return None

            # Create filename: "Artist - Title.mp3"
            base_name = sanitize_filename(f"{channel} - {title}")
            filename = f"{base_name}.mp3"
            output_path = self.download_dir / filename

            # Check if file already exists
            if output_path.exists():
                _safe_print(f"[yellow]File already exists: {filename}[/yellow]")
                return str(output_path)

            _safe_print(f"[cyan]Downloading: {title}[/cyan]")

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

            _safe_print(f"[green]✓ Downloaded: {filename}[/green]")
            return str(output_path)

        except Exception as e:
            logger.exception("Failed to download %s (%s)", video_info.get('title'), video_info.get('video_id'))
            _safe_print(f"[red]✗ Error downloading {video_info.get('title')}: {e}[/red]")
            # If yt-dlp+FFmpeg actually finished (output_path exists), this
            # exception came from something after that -- e.g. tagging, or a
            # console-print failure elsewhere -- so don't glob-delete the
            # finished file; only clean up genuine partial/orphaned output.
            if base_name and not (output_path and output_path.exists()):
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
            logger.warning("Could not tag %s: %s", file_path, e)
            _safe_print(f"[yellow]Warning: Could not tag file: {e}[/yellow]")
