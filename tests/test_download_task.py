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


def test_start_download_releases_guard_if_scheduling_fails(tmp_path, monkeypatch):
    """docs/16, 16-25: if anything between setting _download_in_progress =
    True and successfully scheduling the background task raises, the guard
    must still be released -- otherwise it's stuck True forever with no
    background task ever running to release it via download_task's own
    `finally`, wedging every future /api/download behind a 409."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, '_download_in_progress', False)

    async def call():
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("boom")):
            await routes.start_download(BackgroundTasks())

    try:
        asyncio.run(call())
        raised = None
    except RuntimeError as e:
        raised = e

    assert raised is not None
    assert routes._download_in_progress is False


def test_start_download_refused_on_production_deployment(tmp_path, monkeypatch):
    """The Fly.io deployment must never actually download -- only queue
    (see start_download's docstring). Checked via IS_PRODUCTION
    (environment), not client IP, since Fly proxies every request so the
    app never sees a real client IP to gate on."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, 'IS_PRODUCTION', True)

    async def call():
        await routes.start_download(BackgroundTasks())

    try:
        asyncio.run(call())
        raised = None
    except HTTPException as e:
        raised = e

    assert raised is not None
    assert raised.status_code == 403
    assert 'fly.io' in raised.detail.lower()


def test_start_download_allowed_when_not_production(tmp_path, monkeypatch):
    """Regression guard the other direction -- a non-empty library on a
    non-production deployment must still reach the normal scheduling path,
    not get wrongly refused by the IS_PRODUCTION check."""
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)
    monkeypatch.setattr(routes, 'storage', storage)
    monkeypatch.setattr(routes, 'IS_PRODUCTION', False)
    monkeypatch.setattr(routes, '_download_in_progress', False)

    async def call():
        with patch('asyncio.get_running_loop', return_value=MagicMock()):
            return await routes.start_download(BackgroundTasks())

    result = asyncio.run(call())

    assert 'started downloading' in result['message'].lower()
