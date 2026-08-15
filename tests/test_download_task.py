"""Tests for app/api/routes.py's download_task/start_download -- the thin
API-layer wrapper around app.services.download_orchestrator.run_download_task
(see docs/09, AUD-18). The actual batch-download logic is covered in
tests/test_download_orchestrator.py; this file covers what's specific to
the routes layer: the concurrency lock (AUD-01) and delegation/cleanup.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

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


def test_download_task_delegates_to_orchestrator_and_releases_lock(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, '_download_in_progress', True)

    with patch('app.api.routes.run_download_task') as mock_run:
        routes.download_task(video_ids=None, loop=MagicMock())

    mock_run.assert_called_once()
    # Lock must be released even though we don't call the real orchestrator.
    assert routes._download_in_progress is False


def test_download_task_releases_lock_even_if_orchestrator_raises(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, '_download_in_progress', True)

    with patch('app.api.routes.run_download_task', side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            routes.download_task(video_ids=None, loop=MagicMock())

    assert routes._download_in_progress is False


def test_start_download_rejects_concurrent_calls(tmp_path, monkeypatch):
    """AUD-01: a second /api/download while one is already running must be
    rejected (409), not silently start a second overlapping background task
    that could race the first onto the same output file."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, '_download_in_progress', True)

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
