"""Tests for app/services/download_orchestrator.py's run_download_task --
the core queue/download state machine (docs/09, AUD-18/AUD-19). Previously
had zero coverage; this is the function most likely to silently regress and
least likely to be caught by anything else (the e2e suite mocks search
only, never a real download).

YouTubeDownloader and the WebSocket manager are both mocked/faked; no
network calls, no real files.
"""
import sqlite3
from unittest.mock import MagicMock

from app.services.download_orchestrator import run_download_task
from app.storage.storage import Storage

VIDEO = {
    'video_id': 'abc123',
    'title': 'Test Song',
    'channel': 'Test Channel',
    'duration': '03:00',
    'url': 'https://www.youtube.com/watch?v=abc123',
    'thumbnail': 'https://img.youtube.com/vi/abc123/mqdefault.jpg',
}


def _run(tmp_path, download_audio_result=None, download_audio_side_effect=None, video_ids=None):
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)

    fake_downloader = MagicMock()
    if download_audio_side_effect is not None:
        fake_downloader.download_audio.side_effect = download_audio_side_effect
    else:
        fake_downloader.download_audio.return_value = download_audio_result
    downloader_cls = MagicMock(return_value=fake_downloader)

    mock_manager = MagicMock()

    run_download_task(storage, mock_manager, video_ids, loop=MagicMock(), downloader_cls=downloader_cls)
    return storage, mock_manager


def test_success_records_and_dequeues(tmp_path):
    storage, mock_manager = _run(tmp_path, download_audio_result='/tmp/song.mp3')

    assert storage.get_item_status('abc123') == 'downloaded'
    assert storage.is_in_library('abc123') is False

    downloaded = storage.load_downloaded()
    assert downloaded[0]['success'] is True
    assert downloaded[0]['file_path'] == '/tmp/song.mp3'

    args = mock_manager.broadcast_threadsafe.call_args[0]
    assert args[0] == {"type": "download_complete", "video_id": "abc123", "success": True}


def test_failure_is_recorded_not_discarded(tmp_path):
    """AUD-02: a failed download must not just vanish -- it should be
    queryable via /api/downloaded, and (AUD-03) must not block a retry."""
    storage, mock_manager = _run(tmp_path, download_audio_result=None)

    # Removed from the queue either way (queue must not get stuck)...
    assert storage.is_in_library('abc123') is False
    # ...but recorded as a failure, not silently discarded.
    downloaded = storage.load_downloaded()
    assert len(downloaded) == 1
    assert downloaded[0]['success'] is False
    assert downloaded[0]['file_path'] is None

    # Still not "downloaded" -- can be re-added to the queue and retried.
    assert storage.get_item_status('abc123') == 'new'

    args = mock_manager.broadcast_threadsafe.call_args[0]
    assert args[0] == {"type": "download_complete", "video_id": "abc123", "success": False}


def test_unexpected_exception_is_treated_as_failure(tmp_path):
    """download_audio() raising (rather than returning None) must still be
    recorded as a failure, not crash the whole batch."""
    storage, mock_manager = _run(tmp_path, download_audio_side_effect=RuntimeError("boom"))

    assert storage.is_in_library('abc123') is False
    downloaded = storage.load_downloaded()
    assert downloaded[0]['success'] is False


def test_empty_library_is_a_noop(tmp_path):
    storage = Storage(str(tmp_path))
    mock_manager = MagicMock()

    run_download_task(storage, mock_manager, None, loop=MagicMock())

    mock_manager.broadcast_threadsafe.assert_not_called()


def test_remove_from_library_failure_does_not_abort_the_batch(tmp_path, monkeypatch):
    """docs/16, 16-12: add_to_downloaded() and remove_from_library() are two
    separate SQLite writes with no transaction spanning them. If the second
    write raises, the outcome must still have been recorded (add_to_downloaded
    already ran), and -- the actual fix -- the exception must not propagate
    out of run_download_task and abort the rest of the batch."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    storage.add_to_library({**VIDEO, 'video_id': 'other456'})

    def boom(video_id):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(storage, "remove_from_library", boom)

    fake_downloader = MagicMock()
    fake_downloader.download_audio.return_value = '/tmp/song.mp3'
    downloader_cls = MagicMock(return_value=fake_downloader)

    # Must not raise -- the whole point of the fix.
    run_download_task(storage, MagicMock(), None, loop=MagicMock(), downloader_cls=downloader_cls)

    # The outcome was still recorded for both videos despite remove_from_library
    # always failing (the "duplicated" state 16-12 describes -- still in the
    # library *and* recorded as downloaded -- but not a crashed, half-run batch).
    downloaded = storage.load_downloaded()
    assert {d['video_id'] for d in downloaded} == {'abc123', 'other456'}
    assert all(d['success'] for d in downloaded)


def test_filters_by_video_ids(tmp_path):
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    storage.add_to_library({**VIDEO, 'video_id': 'other456'})

    fake_downloader = MagicMock()
    fake_downloader.download_audio.return_value = '/tmp/song.mp3'
    downloader_cls = MagicMock(return_value=fake_downloader)

    run_download_task(storage, MagicMock(), ['abc123'], loop=MagicMock(), downloader_cls=downloader_cls)

    # Only the requested video was touched.
    assert storage.get_item_status('abc123') == 'downloaded'
    assert storage.get_item_status('other456') == 'queued'
