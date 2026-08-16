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


# ---------------------------------------------------------------------------
# /api/downloaded/record -- Fly-sync push target (docs: "Give the local
# instance a Fly sync mechanism"). Records a download outcome that happened
# elsewhere (a local instance) without running yt-dlp here.
# ---------------------------------------------------------------------------

OUTCOME = {**VIDEO, "success": True, "file_path": "/downloads/Test Song.mp3"}


def test_record_downloaded_externally_adds_history_and_does_not_require_library(tmp_path, monkeypatch):
    """Safe to call for a video_id not currently in the library -- just
    records history."""
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/downloaded/record", json=OUTCOME)

    assert resp.status_code == 200
    assert resp.json()["video_id"] == "abc123"
    assert client.get("/api/status").json()["downloaded_count"] == 1
    downloaded = client.get("/api/downloaded").json()["downloaded"]
    assert downloaded[0]["video_id"] == "abc123"
    assert downloaded[0]["success"] is True


def test_record_downloaded_externally_removes_from_library_if_present(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    client.post("/api/library/add", json=VIDEO)

    resp = client.post("/api/downloaded/record", json=OUTCOME)

    assert resp.status_code == 200
    assert client.get("/api/status").json() == {"library_count": 0, "downloaded_count": 1}


def test_record_downloaded_externally_is_idempotent(tmp_path, monkeypatch):
    """Safe to call more than once for the same video_id -- matches
    add_to_downloaded's upsert (INSERT OR REPLACE) semantics, no duplicate
    rows and no error on the second call."""
    isolated_storage(tmp_path, monkeypatch)

    resp1 = client.post("/api/downloaded/record", json=OUTCOME)
    resp2 = client.post("/api/downloaded/record", json=OUTCOME)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert client.get("/api/status").json()["downloaded_count"] == 1


def test_record_downloaded_externally_records_failures_too(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)

    resp = client.post("/api/downloaded/record", json={**VIDEO, "success": False, "file_path": None})

    assert resp.status_code == 200
    downloaded = client.get("/api/downloaded").json()["downloaded"]
    assert downloaded[0]["success"] is False
    # A failed download must not count as "downloaded" for status purposes.
    assert client.post("/api/statuses", json={"video_ids": ["abc123"]}).json() == {"statuses": {"abc123": "new"}}


# ---------------------------------------------------------------------------
# /api/sync/status and /api/sync/pull -- local-only Fly sync.
# ---------------------------------------------------------------------------

def test_sync_status_unavailable_when_not_configured(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("FLY_SYNC_URL", raising=False)
    monkeypatch.delenv("FLY_SYNC_USERNAME", raising=False)
    monkeypatch.delenv("FLY_SYNC_PASSWORD", raising=False)

    resp = client.get("/api/sync/status")

    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_sync_status_available_when_configured_and_not_production(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", False)
    monkeypatch.setenv("FLY_SYNC_URL", "https://example.fly.dev")
    monkeypatch.setenv("FLY_SYNC_USERNAME", "someone")
    monkeypatch.setenv("FLY_SYNC_PASSWORD", "secret")

    resp = client.get("/api/sync/status")

    assert resp.status_code == 200
    assert resp.json() == {"available": True}


def test_sync_status_unavailable_on_production_even_if_configured(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", True)
    monkeypatch.setenv("FLY_SYNC_URL", "https://example.fly.dev")
    monkeypatch.setenv("FLY_SYNC_USERNAME", "someone")
    monkeypatch.setenv("FLY_SYNC_PASSWORD", "secret")

    resp = client.get("/api/sync/status")

    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_sync_pull_refused_on_production(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", True)

    resp = client.post("/api/sync/pull")

    assert resp.status_code == 403


def test_sync_pull_400_when_not_configured(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", False)
    monkeypatch.delenv("FLY_SYNC_URL", raising=False)
    monkeypatch.delenv("FLY_SYNC_USERNAME", raising=False)
    monkeypatch.delenv("FLY_SYNC_PASSWORD", raising=False)

    resp = client.post("/api/sync/pull")

    assert resp.status_code == 400


def test_sync_pull_adds_only_unknown_items(tmp_path, monkeypatch):
    """Anything already known locally (queued or downloaded) is skipped,
    not re-added -- makes a repeated pull idempotent."""
    storage = isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", False)
    monkeypatch.setenv("FLY_SYNC_URL", "https://example.fly.dev")
    monkeypatch.setenv("FLY_SYNC_USERNAME", "someone")
    monkeypatch.setenv("FLY_SYNC_PASSWORD", "secret")

    # abc123 already queued locally, xyz789 already downloaded locally --
    # both must be skipped. brand_new isn't known locally at all.
    storage.add_to_library(VIDEO)
    storage.add_to_downloaded({**VIDEO, "video_id": "xyz789", "success": True, "file_path": "/x.mp3"})
    brand_new = {**VIDEO, "video_id": "brand_new"}

    remote_library = [VIDEO, {**VIDEO, "video_id": "xyz789"}, brand_new]

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, data=None, json=None):
            assert url == "https://example.fly.dev/login"
            return FakeResponse(303)

        def get(self, url):
            assert url == "https://example.fly.dev/api/library"
            return FakeResponse(200, {"library": remote_library})

    import httpx as httpx_module

    from app.services import fly_sync
    monkeypatch.setattr(fly_sync, "httpx", type("M", (), {"Client": FakeClient, "HTTPError": httpx_module.HTTPError}))

    resp = client.post("/api/sync/pull")

    assert resp.status_code == 200
    body = resp.json()
    assert body["pulled"] == 1
    assert body["skipped"] == 2

    library = client.get("/api/library").json()["library"]
    ids = {v["video_id"] for v in library}
    assert ids == {"abc123", "brand_new"}


def test_sync_pull_surfaces_login_failure_as_502(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "IS_PRODUCTION", False)
    monkeypatch.setenv("FLY_SYNC_URL", "https://example.fly.dev")
    monkeypatch.setenv("FLY_SYNC_USERNAME", "someone")
    monkeypatch.setenv("FLY_SYNC_PASSWORD", "wrong")

    class FakeResponse:
        status_code = 401

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, data=None, json=None):
            return FakeResponse()

        def get(self, url):
            raise AssertionError("should not fetch library after a failed login")

    import httpx as httpx_module

    from app.services import fly_sync
    monkeypatch.setattr(fly_sync, "httpx", type("M", (), {"Client": FakeClient, "HTTPError": httpx_module.HTTPError}))

    resp = client.post("/api/sync/pull")

    assert resp.status_code == 502
