"""Tests for app/services/fly_sync.py -- the local-only bridge between this
instance's SQLite database and a live Fly deployment's. No real HTTP calls
here (see fly_sync's own docstring and this repo's live-verification
precedent, tests/e2e/extension_live_test.js) -- httpx.Client is replaced
with an in-memory fake that records what was called and returns
programmed responses.
"""
import httpx
import pytest

from app.services import fly_sync
from app.storage.storage import Storage

VIDEO = {
    "video_id": "abc123",
    "title": "Test Song",
    "channel": "Test Channel",
    "duration": "03:00",
    "url": "https://www.youtube.com/watch?v=abc123",
    "thumbnail": "https://img.youtube.com/vi/abc123/mqdefault.jpg",
}


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    """Stand-in for httpx.Client. `script` maps (method, path) -> FakeResponse
    (or a callable returning one); records every call made against it in
    `.calls` so tests can assert on cookies/sequencing without a real
    server."""

    instances = []

    def __init__(self, script, raise_on=None):
        self.script = script
        self.raise_on = raise_on or set()
        self.calls = []

    def __call__(self, timeout=None):
        # Lets a single FakeClient factory be passed as `httpx.Client`.
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _handle(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        key = (method, url)
        if key in self.raise_on:
            raise httpx.ConnectError("simulated network failure")
        if key not in self.script:
            raise AssertionError(f"unscripted call: {method} {url}")
        result = self.script[key]
        return result() if callable(result) else result

    def post(self, url, data=None, json=None):
        return self._handle("POST", url, data=data, json=json)

    def get(self, url):
        return self._handle("GET", url)

    def delete(self, url):
        return self._handle("DELETE", url)


def _patch_client(monkeypatch, fake_client):
    monkeypatch.setattr(fly_sync, "httpx", type("M", (), {"Client": fake_client, "HTTPError": httpx.HTTPError}))


def _configure(monkeypatch, url="https://example.fly.dev", username="someone", password="secret"):
    monkeypatch.setenv("FLY_SYNC_URL", url)
    monkeypatch.setenv("FLY_SYNC_USERNAME", username)
    monkeypatch.setenv("FLY_SYNC_PASSWORD", password)


def test_is_configured_false_when_any_var_missing(monkeypatch):
    monkeypatch.delenv("FLY_SYNC_URL", raising=False)
    monkeypatch.delenv("FLY_SYNC_USERNAME", raising=False)
    monkeypatch.delenv("FLY_SYNC_PASSWORD", raising=False)
    assert fly_sync.is_configured() is False

    _configure(monkeypatch)
    monkeypatch.delenv("FLY_SYNC_PASSWORD", raising=False)
    assert fly_sync.is_configured() is False


def test_is_configured_true_when_all_set(monkeypatch):
    _configure(monkeypatch)
    assert fly_sync.is_configured() is True


def test_pull_raises_if_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("FLY_SYNC_URL", raising=False)
    storage = Storage(str(tmp_path))
    with pytest.raises(fly_sync.FlySyncError):
        fly_sync.pull_from_fly(storage)


def test_pull_skips_items_already_known_locally(tmp_path, monkeypatch):
    _configure(monkeypatch)
    storage = Storage(str(tmp_path))
    storage.add_to_library(VIDEO)  # already queued locally

    remote_library = [VIDEO, {**VIDEO, "video_id": "brand_new"}]
    fake = FakeClient({
        ("POST", "https://example.fly.dev/login"): FakeResponse(303),
        ("GET", "https://example.fly.dev/api/library"): FakeResponse(200, {"library": remote_library}),
    })
    _patch_client(monkeypatch, fake)

    result = fly_sync.pull_from_fly(storage)

    assert result == {"pulled": 1, "skipped": 1}
    ids = {v["video_id"] for v in storage.load_library()}
    assert ids == {"abc123", "brand_new"}


def test_pull_is_idempotent_on_repeat_call(tmp_path, monkeypatch):
    _configure(monkeypatch)
    storage = Storage(str(tmp_path))
    remote_library = [VIDEO]
    fake = FakeClient({
        ("POST", "https://example.fly.dev/login"): FakeResponse(303),
        ("GET", "https://example.fly.dev/api/library"): FakeResponse(200, {"library": remote_library}),
    })
    _patch_client(monkeypatch, fake)

    first = fly_sync.pull_from_fly(storage)
    second = fly_sync.pull_from_fly(storage)

    assert first == {"pulled": 1, "skipped": 0}
    assert second == {"pulled": 0, "skipped": 1}
    assert len(storage.load_library()) == 1


def test_pull_raises_flysyncerror_on_bad_login(tmp_path, monkeypatch):
    _configure(monkeypatch)
    storage = Storage(str(tmp_path))
    fake = FakeClient({("POST", "https://example.fly.dev/login"): FakeResponse(401)})
    _patch_client(monkeypatch, fake)

    with pytest.raises(fly_sync.FlySyncError):
        fly_sync.pull_from_fly(storage)


def test_pull_raises_flysyncerror_on_network_error(tmp_path, monkeypatch):
    _configure(monkeypatch)
    storage = Storage(str(tmp_path))
    fake = FakeClient({}, raise_on={("POST", "https://example.fly.dev/login")})
    _patch_client(monkeypatch, fake)

    with pytest.raises(fly_sync.FlySyncError):
        fly_sync.pull_from_fly(storage)


def test_push_is_noop_when_not_configured(monkeypatch):
    monkeypatch.delenv("FLY_SYNC_URL", raising=False)
    fake = FakeClient({})
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": True, "file_path": "/x.mp3"})

    assert fake.calls == []  # never even constructed a client call


def test_push_records_then_removes_from_remote_library(monkeypatch):
    _configure(monkeypatch)
    fake = FakeClient({
        ("POST", "https://example.fly.dev/login"): FakeResponse(303),
        ("POST", "https://example.fly.dev/api/downloaded/record"): FakeResponse(200, {"message": "Recorded"}),
        ("DELETE", "https://example.fly.dev/api/library/abc123"): FakeResponse(200, {"message": "Removed"}),
    })
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": True, "file_path": "/x.mp3"})

    methods_urls = [(m, u) for m, u, _ in fake.calls]
    assert methods_urls == [
        ("POST", "https://example.fly.dev/login"),
        ("POST", "https://example.fly.dev/api/downloaded/record"),
        ("DELETE", "https://example.fly.dev/api/library/abc123"),
    ]
    record_call = fake.calls[1]
    assert record_call[2]["json"]["success"] is True
    assert record_call[2]["json"]["video_id"] == "abc123"


def test_push_records_failures_too(monkeypatch):
    _configure(monkeypatch)
    fake = FakeClient({
        ("POST", "https://example.fly.dev/login"): FakeResponse(303),
        ("POST", "https://example.fly.dev/api/downloaded/record"): FakeResponse(200, {}),
        ("DELETE", "https://example.fly.dev/api/library/abc123"): FakeResponse(200, {}),
    })
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": False, "file_path": None})

    record_call = fake.calls[1]
    assert record_call[2]["json"]["success"] is False
    assert record_call[2]["json"]["file_path"] is None


def test_push_never_raises_on_login_failure(monkeypatch):
    """Push is best-effort -- must never propagate, since it runs right
    after a real local download has already succeeded/failed."""
    _configure(monkeypatch)
    fake = FakeClient({("POST", "https://example.fly.dev/login"): FakeResponse(401)})
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": True, "file_path": "/x.mp3"})  # must not raise


def test_push_never_raises_on_network_error(monkeypatch):
    _configure(monkeypatch)
    fake = FakeClient({}, raise_on={("POST", "https://example.fly.dev/login")})
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": True, "file_path": "/x.mp3"})  # must not raise


def test_push_never_raises_when_record_endpoint_errors(monkeypatch):
    _configure(monkeypatch)
    fake = FakeClient({
        ("POST", "https://example.fly.dev/login"): FakeResponse(303),
        ("POST", "https://example.fly.dev/api/downloaded/record"): FakeResponse(500),
    })
    _patch_client(monkeypatch, fake)

    fly_sync.push_download_outcome({**VIDEO, "success": True, "file_path": "/x.mp3"})  # must not raise
    # Must not attempt the DELETE after a failed record.
    methods_urls = [(m, u) for m, u, _ in fake.calls]
    assert ("DELETE", "https://example.fly.dev/api/library/abc123") not in methods_urls
