"""Tests for app/services/downloader.py's failure handling (no real downloads)."""
from unittest.mock import patch

from app.services.downloader import YouTubeDownloader

VIDEO = {
    'video_id': 'abc123',
    'title': 'Test Song',
    'channel': 'Test Channel',
    'duration': '03:00',
    'url': 'https://www.youtube.com/watch?v=abc123',
}


def test_download_audio_fails_fast_without_ffmpeg(tmp_path):
    downloader = YouTubeDownloader(download_dir=str(tmp_path))

    with patch('app.services.downloader.shutil.which', return_value=None), \
         patch('app.services.downloader.yt_dlp.YoutubeDL') as mock_ydl:
        result = downloader.download_audio(VIDEO)

    assert result is None
    mock_ydl.assert_not_called()  # never even attempts a network download
    assert list(tmp_path.iterdir()) == []  # nothing left behind


def test_cleanup_partial_download_removes_matching_files(tmp_path):
    downloader = YouTubeDownloader(download_dir=str(tmp_path))
    leftover = tmp_path / "Test Channel - Test Song.webm"
    leftover.write_bytes(b"not actually mp3 data")
    unrelated = tmp_path / "Other Channel - Other Song.mp3"
    unrelated.write_bytes(b"unrelated file")

    downloader._cleanup_partial_download("Test Channel - Test Song")

    assert not leftover.exists()
    assert unrelated.exists()  # doesn't touch files for other downloads


def test_download_audio_cleans_up_on_conversion_failure(tmp_path):
    downloader = YouTubeDownloader(download_dir=str(tmp_path))

    def fake_download(self, urls):
        # Simulate yt-dlp writing the raw pre-conversion file, then the
        # FFmpeg postprocessor failing.
        (tmp_path / "Test Channel - Test Song.webm").write_bytes(b"raw audio")
        raise RuntimeError("ffmpeg postprocessing failed")

    with patch('app.services.downloader.shutil.which', return_value='/usr/bin/ffmpeg'), \
         patch('yt_dlp.YoutubeDL.YoutubeDL.download', fake_download):
        result = downloader.download_audio(VIDEO)

    assert result is None
    assert list(tmp_path.iterdir()) == []  # orphaned raw file was cleaned up
