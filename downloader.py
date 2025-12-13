"""YouTube downloader with progress tracking and metadata tagging."""
from pathlib import Path

import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

from utils import sanitize_filename

console = Console()


class YouTubeDownloader:
    """Handles downloading YouTube videos as MP3 files."""

    def __init__(self, download_dir: str = "./downloads", audio_quality: str = "320"):
        self.download_dir = Path(download_dir)
        self.audio_quality = audio_quality
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.progress = None
        self.task_id = None

    def _progress_hook(self, d):
        """Progress callback for yt-dlp."""
        if self.progress is None:
            return

        if d['status'] == 'downloading':
            # Update progress bar
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)

            if total > 0 and self.task_id is not None:
                self.progress.update(self.task_id, completed=downloaded, total=total)

        elif d['status'] == 'finished':
            if self.task_id is not None:
                self.progress.update(self.task_id, completed=100, total=100)

    def download_audio(self, video_info: dict) -> str | None:
        """Download video as MP3 audio file."""
        try:
            url = video_info['url']
            title = video_info['title']
            channel = video_info['channel']

            # Create filename: "Artist - Title.mp3"
            filename = sanitize_filename(f"{channel} - {title}.mp3")
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
                'outtmpl': str(self.download_dir / sanitize_filename(f"{channel} - {title}")),
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
            return None

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
