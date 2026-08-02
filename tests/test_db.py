"""Tests for app/storage/db.py's SQLite-backed library/downloaded storage."""
import pytest

from app.storage.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def make_video(video_id="abc123"):
    return {
        "video_id": video_id,
        "title": "Test Song",
        "channel": "Test Channel",
        "duration": "03:30",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }


def test_library_add_and_get(db):
    db.add_library_item(make_video(), added_at="2026-01-01 00:00:00")
    library = db.get_library()
    assert len(library) == 1
    assert library[0]["video_id"] == "abc123"


def test_library_is_in_library(db):
    assert db.is_in_library("abc123") is False
    db.add_library_item(make_video(), added_at="2026-01-01 00:00:00")
    assert db.is_in_library("abc123") is True


def test_library_remove(db):
    db.add_library_item(make_video(), added_at="2026-01-01 00:00:00")
    db.remove_library_item("abc123")
    assert db.get_library() == []


def test_library_clear(db):
    db.add_library_item(make_video("a"), added_at="2026-01-01 00:00:00")
    db.add_library_item(make_video("b"), added_at="2026-01-01 00:00:00")
    db.clear_library()
    assert db.count_library() == 0


def test_library_add_duplicate_video_id_replaces(db):
    db.add_library_item(make_video(), added_at="2026-01-01 00:00:00")
    db.add_library_item(make_video(), added_at="2026-01-02 00:00:00")
    assert db.count_library() == 1


def test_downloaded_add_and_get(db):
    item = {**make_video(), "success": True, "file_path": "downloads/test.mp3"}
    db.add_downloaded_item(item, downloaded_at="2026-01-01 00:00:00")
    downloaded = db.get_downloaded()
    assert len(downloaded) == 1
    assert downloaded[0]["success"] is True
    assert downloaded[0]["file_path"] == "downloads/test.mp3"


def test_downloaded_is_downloaded(db):
    assert db.is_downloaded("abc123") is False
    item = {**make_video(), "success": True, "file_path": "downloads/test.mp3"}
    db.add_downloaded_item(item, downloaded_at="2026-01-01 00:00:00")
    assert db.is_downloaded("abc123") is True


def test_downloaded_failed_download_stores_no_file_path(db):
    item = {**make_video(), "success": False, "file_path": None}
    db.add_downloaded_item(item, downloaded_at="2026-01-01 00:00:00")
    downloaded = db.get_downloaded()
    assert downloaded[0]["success"] is False
    assert downloaded[0]["file_path"] is None


def test_counts(db):
    assert db.count_library() == 0
    assert db.count_downloaded() == 0
    db.add_library_item(make_video("a"), added_at="2026-01-01 00:00:00")
    db.add_downloaded_item(
        {**make_video("b"), "success": True, "file_path": "x.mp3"}, downloaded_at="2026-01-01 00:00:00"
    )
    assert db.count_library() == 1
    assert db.count_downloaded() == 1
