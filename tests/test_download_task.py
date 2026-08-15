"""Tests for app/api/routes.py's download_task -- the queue/download state
machine. Previously had zero coverage (docs/09, AUD-19); this is the
function most likely to silently regress and least likely to be caught by
anything else (the e2e suite mocks search only, never a real download).

YouTubeDownloader and the WebSocket manager are both mocked; no network
calls, no real files.
"""
from unittest.mock import MagicMock, patch

from app.api import routes
from app.storage.storage import Storage

VIDEO = {
    'video_id': 'abc123',
    'title': 'Test Song',
    'channel': 'Test Channel',
    'duration': '03:00',
    'url': 'https://www.youtube.com/watch?v=abc123',
    'thumbnail': 'https://img.youtube.com/vi/abc123/mqdefault.jpg',
}


def _run_download_task(tmp_path, monkeypatch, download_audio_result):
    """Set up an isolated Storage, queue one video, run download_task with a
    fake downloader, and return the Storage so the caller can assert on it."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)

    fake_downloader = MagicMock()
    fake_downloader.download_audio.return_value = download_audio_result
    monkeypatch.setattr(routes, 'YouTubeDownloader', MagicMock(return_value=fake_downloader))

    mock_manager = MagicMock()
    monkeypatch.setattr(routes, 'manager', mock_manager)

    routes.download_task(video_ids=None, loop=MagicMock())
    return storage, mock_manager


def test_download_task_success_records_and_dequeues(tmp_path, monkeypatch):
    storage, mock_manager = _run_download_task(tmp_path, monkeypatch, download_audio_result='/tmp/song.mp3')

    assert storage.get_item_status('abc123') == 'downloaded'
    assert storage.is_in_library('abc123') is False

    downloaded = storage.load_downloaded()
    assert downloaded[0]['success'] is True
    assert downloaded[0]['file_path'] == '/tmp/song.mp3'

    args = mock_manager.broadcast_threadsafe.call_args[0]
    assert args[0] == {"type": "download_complete", "video_id": "abc123", "success": True}


def test_download_task_failure_is_recorded_not_discarded(tmp_path, monkeypatch):
    """AUD-02: a failed download must not just vanish -- it should be
    queryable via /api/downloaded, and (AUD-03) must not block a retry."""
    storage, mock_manager = _run_download_task(tmp_path, monkeypatch, download_audio_result=None)

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


def test_download_task_unexpected_exception_is_treated_as_failure(tmp_path, monkeypatch):
    """download_audio() raising (rather than returning None) must still be
    recorded as a failure, not crash the whole batch."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)

    fake_downloader = MagicMock()
    fake_downloader.download_audio.side_effect = RuntimeError("boom")
    monkeypatch.setattr(routes, 'YouTubeDownloader', MagicMock(return_value=fake_downloader))
    monkeypatch.setattr(routes, 'manager', MagicMock())

    routes.download_task(video_ids=None, loop=MagicMock())

    assert storage.is_in_library('abc123') is False
    downloaded = storage.load_downloaded()
    assert downloaded[0]['success'] is False


def test_download_task_empty_library_is_a_noop(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(routes, 'storage', storage)
    mock_manager = MagicMock()
    monkeypatch.setattr(routes, 'manager', mock_manager)

    routes.download_task(video_ids=None, loop=MagicMock())

    mock_manager.broadcast_threadsafe.assert_not_called()


def test_download_task_filters_by_video_ids(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    storage.add_to_library({**VIDEO, 'video_id': 'other456'})
    monkeypatch.setattr(routes, 'storage', storage)

    fake_downloader = MagicMock()
    fake_downloader.download_audio.return_value = '/tmp/song.mp3'
    monkeypatch.setattr(routes, 'YouTubeDownloader', MagicMock(return_value=fake_downloader))
    monkeypatch.setattr(routes, 'manager', MagicMock())

    routes.download_task(video_ids=['abc123'], loop=MagicMock())

    # Only the requested video was touched.
    assert storage.get_item_status('abc123') == 'downloaded'
    assert storage.get_item_status('other456') == 'queued'


def test_start_download_rejects_concurrent_calls(tmp_path, monkeypatch):
    """AUD-01: a second /api/download while one is already running must be
    rejected (409), not silently start a second overlapping background task
    that could race the first onto the same output file."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, '_download_in_progress', True)

    import asyncio

    from fastapi import BackgroundTasks, HTTPException

    async def call():
        with patch('asyncio.get_running_loop', return_value=MagicMock()):
            await routes.start_download(BackgroundTasks())

    try:
        asyncio.run(call())
        raised = None
    except HTTPException as e:
        raised = e

    assert raised is not None
    assert raised.status_code == 409
