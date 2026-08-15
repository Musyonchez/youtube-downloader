"""Tests for the /history page and its data source (docs/09, AUD-26)."""
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.storage.storage import Storage
from tests.conftest import log_in_test_client

client = TestClient(app)


def test_history_page_renders(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "storage", Storage(str(tmp_path)))
    log_in_test_client(client, tmp_path, monkeypatch)
    resp = client.get("/history")
    assert resp.status_code == 200
    assert "Download History" in resp.text
    assert 'id="results-grid"' in resp.text


def test_history_navbar_link_marked_active(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "storage", Storage(str(tmp_path)))
    log_in_test_client(client, tmp_path, monkeypatch)
    resp = client.get("/history")
    assert 'href="/history" class="active"' in resp.text


def test_downloaded_endpoint_includes_both_success_and_failure(tmp_path, monkeypatch):
    """The history page's data source -- confirms failed downloads (AUD-02)
    are actually visible through the same endpoint the page reads from."""
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(routes, "storage", storage)
    log_in_test_client(client, tmp_path, monkeypatch)

    video = {
        "video_id": "abc123",
        "title": "Test Song",
        "channel": "Test Channel",
        "duration": "03:00",
        "url": "https://www.youtube.com/watch?v=abc123",
        "thumbnail": "https://img.youtube.com/vi/abc123/mqdefault.jpg",
    }
    storage.add_to_downloaded({**video, "success": True, "file_path": "x.mp3"})
    storage.add_to_downloaded({**video, "video_id": "failed1", "success": False, "file_path": None})

    resp = client.get("/api/downloaded")
    downloaded = resp.json()["downloaded"]

    assert len(downloaded) == 2
    assert any(d["success"] and d["video_id"] == "abc123" for d in downloaded)
    assert any(not d["success"] and d["video_id"] == "failed1" for d in downloaded)
