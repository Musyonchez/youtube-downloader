"""HTTP-level tests for the library/config/status routes (docs/09, AUD-20).

Deliberately scoped to routes that never touch the network (no search,
video-info, playlist-info, or download endpoints here -- those go through
yt-dlp and are exercised at the unit level instead, same reasoning as
test_api_validation.py). Each test points app.api.routes.storage at a
fresh, isolated Storage so nothing here touches the real data/ directory.
"""
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.storage.storage import Storage
from tests.conftest import log_in_test_client

client = TestClient(app)

VIDEO = {
    "video_id": "abc123",
    "title": "Test Song",
    "channel": "Test Channel",
    "duration": "03:00",
    "url": "https://www.youtube.com/watch?v=abc123",
    "thumbnail": "https://img.youtube.com/vi/abc123/mqdefault.jpg",
}


def isolated_storage(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(routes, "storage", storage)
    # These routes are all session-protected now (docs/15) -- see
    # tests/conftest.py's log_in_test_client for why.
    log_in_test_client(client, tmp_path, monkeypatch)
    return storage


def test_status_reflects_empty_storage(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json() == {"library_count": 0, "downloaded_count": 0}


def test_add_to_library_rejects_url_with_disallowed_host(tmp_path, monkeypatch):
    """docs/16, 16-10: /api/video-info and /api/playlist-info already run
    their url through searcher.validate_url's host allowlist; this route
    accepts an arbitrary `url` field directly (not necessarily one that
    came from a search result) and hands it straight to yt-dlp at download
    time, so it needs the same check."""
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/library/add", json={**VIDEO, "url": "https://evil.example.com/?x=youtube.com"})

    assert resp.status_code == 400
    library = client.get("/api/library").json()["library"]
    assert library == []


def test_add_to_library_then_appears_in_library_and_status(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/library/add", json=VIDEO)
    assert resp.status_code == 200
    assert resp.json()["video_id"] == "abc123"

    library = client.get("/api/library").json()["library"]
    assert len(library) == 1
    assert library[0]["video_id"] == "abc123"

    status = client.get("/api/status").json()
    assert status["library_count"] == 1


def test_add_to_library_rejects_duplicate_queued(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    client.post("/api/library/add", json=VIDEO)
    resp = client.post("/api/library/add", json=VIDEO)

    assert resp.status_code == 400
    assert "queue" in resp.json()["detail"].lower()


def test_add_to_library_rejects_already_downloaded(tmp_path, monkeypatch):
    storage = isolated_storage(tmp_path, monkeypatch)
    storage.add_to_downloaded({**VIDEO, "success": True, "file_path": "x.mp3"})

    resp = client.post("/api/library/add", json=VIDEO)

    assert resp.status_code == 400
    assert "downloaded" in resp.json()["detail"].lower()


def test_failed_download_can_be_re_added_to_library(tmp_path, monkeypatch):
    """AUD-02/AUD-03: a failed download is recorded but must not permanently
    block re-queueing -- add_to_library should accept it."""
    storage = isolated_storage(tmp_path, monkeypatch)
    storage.add_to_downloaded({**VIDEO, "success": False, "file_path": None})

    resp = client.post("/api/library/add", json=VIDEO)

    assert resp.status_code == 200
    assert client.get("/api/library").json()["library"][0]["video_id"] == "abc123"


def test_remove_from_library(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    client.post("/api/library/add", json=VIDEO)

    resp = client.delete(f"/api/library/{VIDEO['video_id']}")

    assert resp.status_code == 200
    assert client.get("/api/library").json()["library"] == []


def test_remove_from_library_nonexistent_id_is_still_200(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    resp = client.delete("/api/library/does-not-exist")
    assert resp.status_code == 200


def test_clear_library(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    client.post("/api/library/add", json=VIDEO)
    client.post("/api/library/add", json={**VIDEO, "video_id": "other456"})

    resp = client.delete("/api/library")

    assert resp.status_code == 200
    assert client.get("/api/library").json()["library"] == []


def test_get_downloaded_history(tmp_path, monkeypatch):
    storage = isolated_storage(tmp_path, monkeypatch)
    storage.add_to_downloaded({**VIDEO, "success": True, "file_path": "x.mp3"})
    storage.add_to_downloaded({**VIDEO, "video_id": "failed1", "success": False, "file_path": None})

    resp = client.get("/api/downloaded")

    assert resp.status_code == 200
    downloaded = resp.json()["downloaded"]
    assert len(downloaded) == 2
    assert {d["success"] for d in downloaded} == {True, False}


def test_get_downloaded_history_is_paginated_newest_first(tmp_path, monkeypatch):
    """docs/16, 16-8: /api/downloaded bounds what it returns per call and
    reports `total` separately, instead of always returning the entire
    (ever-growing) history table."""
    storage = isolated_storage(tmp_path, monkeypatch)
    # Explicit, distinct downloaded_at timestamps (bypassing
    # add_to_downloaded's "now") -- three inserts in the same test could
    # otherwise land in the same second and make ordering ambiguous.
    for i in range(3):
        storage.db.add_downloaded_item(
            {**VIDEO, "video_id": f"v{i}", "success": True, "file_path": "x.mp3"},
            downloaded_at=f"2026-01-0{i + 1} 00:00:00",
        )

    resp = client.get("/api/downloaded?limit=2&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert [d["video_id"] for d in body["downloaded"]] == ["v2", "v1"]  # newest first

    next_page = client.get("/api/downloaded?limit=2&offset=2")
    assert [d["video_id"] for d in next_page.json()["downloaded"]] == ["v0"]


def test_get_and_update_config(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    initial = client.get("/api/config").json()
    assert initial["audio_quality"] == "320"

    resp = client.post("/api/config", json={"audio_quality": "192"})
    assert resp.status_code == 200

    updated = client.get("/api/config").json()
    assert updated["audio_quality"] == "192"
    # download_dir wasn't part of this update -- must be untouched.
    assert updated["download_dir"] == initial["download_dir"]


def test_update_config_rejects_sensitive_download_dir(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    import os
    sensitive = os.environ.get('WINDIR', 'C:/Windows') if os.name == 'nt' else '/etc'
    resp = client.post("/api/config", json={"download_dir": sensitive})

    assert resp.status_code == 400


def test_update_config_accepts_normal_download_dir(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/config", json={"download_dir": "./my-downloads"})

    assert resp.status_code == 200
    assert client.get("/api/config").json()["download_dir"] == "./my-downloads"


def test_add_multiple_endpoint_was_removed(tmp_path, monkeypatch):
    """AUD-12: the dead bulk-add endpoint (never wired to any UI) was
    removed -- regression guard against accidentally re-adding it."""
    isolated_storage(tmp_path, monkeypatch)
    resp = client.post("/api/library/add-multiple", json=[VIDEO])
    assert resp.status_code in (404, 405)


def test_get_statuses_batch_lookup(tmp_path, monkeypatch):
    """Used by the extension's on-page thumbnail badges (extension/content.js)
    to resolve new/queued/downloaded state for many video IDs in one call
    instead of one /api/video-info per thumbnail."""
    isolated_storage(tmp_path, monkeypatch)

    client.post("/api/library/add", json=VIDEO)

    resp = client.post("/api/statuses", json={"video_ids": ["abc123", "unknown999"]})

    assert resp.status_code == 200
    assert resp.json() == {"statuses": {"abc123": "queued", "unknown999": "new"}}


def test_get_statuses_rejects_over_200_ids(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/statuses", json={"video_ids": [f"id{i}" for i in range(201)]})

    assert resp.status_code == 422
