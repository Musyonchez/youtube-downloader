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
    return storage


def test_status_reflects_empty_storage(tmp_path, monkeypatch):
    isolated_storage(tmp_path, monkeypatch)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json() == {"library_count": 0, "downloaded_count": 0}


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
