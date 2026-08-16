"""Shared test helpers.

log_in_test_client() exists because docs/15's session auth now protects
every /api/* route and every /app/*, /history page -- route-level tests
written before that (test_api_routes.py, test_history_page.py) need a
valid session to keep testing what they were actually testing, without
turning every one of those tests into an auth test too (see
tests/test_auth_routes.py for the actual auth-boundary tests).
"""
from app import main
from app.passwords import hash_password
from app.storage.storage import Storage


def log_in_test_client(client, tmp_path, monkeypatch):
    """Point app.main.auth_storage at an isolated, throwaway Storage (a
    subdirectory of the test's own tmp_path -- never the real data/
    directory), create a single test account in it, and log the given
    TestClient in against it. Safe to call once per test even though the
    TestClient's cookie jar persists across a whole test module -- logging
    in again is idempotent."""
    auth_storage = Storage(str(tmp_path / "_auth"))
    auth_storage.create_user("testuser", hash_password("testpass123"))
    monkeypatch.setattr(main, "auth_storage", auth_storage)
    # Login rate limiting (docs/16, 16-2) tracks failed attempts in a
    # module-level dict keyed by username -- reset it per test so an
    # unrelated earlier test's failures for the same username (e.g.
    # "testuser") can't leave this login stuck in a cooldown.
    monkeypatch.setattr(main, "_failed_login_attempts", {})
    # registration_open()'s module-level cache (docs/16, 16-16) latches
    # True forever once any test's storage shows count_users() > 0 --
    # reset it per test too, or a later test with a fresh, empty isolated
    # storage would still see registration as closed.
    monkeypatch.setattr(main, "_registration_closed_cache", False)
    resp = client.post("/login", data={"username": "testuser", "password": "testpass123"})
    assert resp.status_code in (200, 303), f"test helper login failed: {resp.status_code} {resp.text}"
