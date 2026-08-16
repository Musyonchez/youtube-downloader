"""Tests for app/storage/db.py's SQLite-backed library/downloaded storage."""
import sqlite3

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


def test_downloaded_failed_download_is_not_is_downloaded(db):
    """A failed attempt is recorded (for history/debugging) but must not
    block the video from being re-queued -- is_downloaded() should only
    match success=1 rows, not mere row presence."""
    item = {**make_video(), "success": False, "file_path": None}
    db.add_downloaded_item(item, downloaded_at="2026-01-01 00:00:00")
    assert db.is_downloaded("abc123") is False


def test_downloaded_pagination_limit_and_offset(db):
    """docs/16, 16-8: get_downloaded's limit/offset actually bound and
    page through the result set instead of always returning everything."""
    for i in range(5):
        db.add_downloaded_item(
            {**make_video(f"v{i}"), "success": True, "file_path": "x.mp3"},
            downloaded_at=f"2026-01-0{i + 1} 00:00:00",
        )

    first_page = db.get_downloaded(limit=2, offset=0)
    second_page = db.get_downloaded(limit=2, offset=2)
    remainder = db.get_downloaded(limit=2, offset=4)

    assert [r["video_id"] for r in first_page] == ["v0", "v1"]
    assert [r["video_id"] for r in second_page] == ["v2", "v3"]
    assert [r["video_id"] for r in remainder] == ["v4"]


def test_downloaded_pagination_descending(db):
    """docs/16, 16-8: `descending=True` returns newest-first, so the
    /history page can page from the newest end without fetching everything
    and reversing it client-side."""
    for i in range(3):
        db.add_downloaded_item(
            {**make_video(f"v{i}"), "success": True, "file_path": "x.mp3"},
            downloaded_at=f"2026-01-0{i + 1} 00:00:00",
        )

    newest_first = db.get_downloaded(descending=True)

    assert [r["video_id"] for r in newest_first] == ["v2", "v1", "v0"]


def test_downloaded_no_limit_returns_everything(db):
    """limit=None (the default) keeps the old unbounded behavior for
    callers that genuinely want the whole table."""
    for i in range(3):
        db.add_downloaded_item(
            {**make_video(f"v{i}"), "success": True, "file_path": "x.mp3"},
            downloaded_at=f"2026-01-0{i + 1} 00:00:00",
        )

    assert len(db.get_downloaded()) == 3


def test_get_statuses_batch(db):
    db.add_library_item(make_video("queued1"), added_at="2026-01-01 00:00:00")
    db.add_downloaded_item(
        {**make_video("done1"), "success": True, "file_path": "x.mp3"}, downloaded_at="2026-01-01 00:00:00"
    )
    db.add_downloaded_item(
        {**make_video("failed1"), "success": False, "file_path": None}, downloaded_at="2026-01-01 00:00:00"
    )

    statuses = db.get_statuses(["queued1", "done1", "failed1", "new1"])

    assert statuses == {
        "queued1": "queued",
        "done1": "downloaded",
        "failed1": "new",  # failed download is re-queueable, reads as 'new'
        "new1": "new",
    }


def test_get_statuses_empty_list(db):
    assert db.get_statuses([]) == {}


def test_counts(db):
    assert db.count_library() == 0
    assert db.count_downloaded() == 0
    db.add_library_item(make_video("a"), added_at="2026-01-01 00:00:00")
    db.add_downloaded_item(
        {**make_video("b"), "success": True, "file_path": "x.mp3"}, downloaded_at="2026-01-01 00:00:00"
    )
    assert db.count_library() == 1
    assert db.count_downloaded() == 1


# User operations (docs/15 -- single-account session auth)

def test_users_create_and_get(db):
    db.create_user("alice", "pbkdf2_sha256$260000$salt$hash", created_at="2026-01-01 00:00:00")
    user = db.get_user("alice")
    assert user is not None
    assert user["username"] == "alice"
    assert user["password_hash"] == "pbkdf2_sha256$260000$salt$hash"


def test_users_get_nonexistent_returns_none(db):
    assert db.get_user("nobody") is None


def test_users_count(db):
    assert db.count_users() == 0
    db.create_user("alice", "hash1", created_at="2026-01-01 00:00:00")
    assert db.count_users() == 1


def test_users_duplicate_username_rejected(db):
    """The actual security boundary for "registration is first-user-only"
    -- a second create_user() for the same username must fail loudly, not
    silently overwrite the existing account's password hash."""
    db.create_user("alice", "hash1", created_at="2026-01-01 00:00:00")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("alice", "hash2", created_at="2026-01-02 00:00:00")
    # Original hash must be untouched by the rejected attempt.
    assert db.get_user("alice")["password_hash"] == "hash1"


def test_create_user_if_first_succeeds_when_empty(db):
    """docs/16, 16-1: the atomic path used by register_submit."""
    created = db.create_user_if_first("alice", "hash1", created_at="2026-01-01 00:00:00")
    assert created is True
    assert db.count_users() == 1
    assert db.get_user("alice")["password_hash"] == "hash1"


def test_create_user_if_first_refuses_second_account(db):
    """The actual registration-race fix (docs/16, 16-1): unlike the old
    "count_users() == 0, then create_user()" (two separate calls), this is
    one atomic check-and-insert -- a second call for a *different*
    username is refused just as reliably as a same-username collision."""
    assert db.create_user_if_first("alice", "hash1", created_at="2026-01-01 00:00:00") is True
    assert db.create_user_if_first("mallory", "hash2", created_at="2026-01-02 00:00:00") is False
    assert db.count_users() == 1
    assert db.get_user("mallory") is None
