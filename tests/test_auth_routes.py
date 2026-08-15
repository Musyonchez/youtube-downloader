"""HTTP-level tests for session-cookie auth routes (docs/15).

Each test gets its own TestClient (own cookie jar) plus an isolated Storage
pointed at tmp_path, monkeypatched onto app.main.auth_storage -- same
per-test isolation as tests/test_api_routes.py's `isolated_storage`, but a
fresh client per test too here, since a shared module-level client would
leak session cookies between tests the way test_api_routes.py's stateless
routes never had to worry about.
"""
import sqlite3

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import main
from app.main import app
from app.storage.storage import Storage


def isolated_client(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(main, "auth_storage", storage)
    return TestClient(app), storage


def test_register_with_zero_users_succeeds_and_starts_session(tmp_path, monkeypatch):
    client, storage = isolated_client(tmp_path, monkeypatch)

    resp = client.post(
        "/register", data={"username": "alice", "password": "hunter22"}, follow_redirects=False
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/app/name"
    assert storage.count_users() == 1
    assert "session" in resp.cookies

    # The session set during registration is real -- a follow-up request
    # with those cookies reaches a protected API route.
    status = client.get("/api/status")
    assert status.status_code == 200


def test_register_refused_when_already_closed_even_via_direct_post(tmp_path, monkeypatch):
    """The actual security boundary (docs/15): a second registration
    attempt hit directly, bypassing the UI/GET redirect entirely, must
    still be refused server-side."""
    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("existing", "pbkdf2_sha256$260000$c2FsdA==$aGFzaA==")

    resp = client.post(
        "/register", data={"username": "mallory", "password": "whatever1"}, follow_redirects=False
    )

    assert resp.status_code == 403
    # No second account was created, and the attempted registration did
    # not get a session either.
    assert storage.count_users() == 1
    assert storage.get_user("mallory") is None
    assert "session" not in resp.cookies


def test_register_race_condition_loser_gets_403_and_no_session(tmp_path, monkeypatch):
    """The IntegrityError backstop (docs/15) end-to-end: two requests can
    both pass register_submit's count_users() == 0 check before either
    commits. test_db.py's test_users_duplicate_username_rejected already
    covers the raw IntegrityError at the storage layer; this simulates the
    actual race by making create_user raise it even though the route's own
    pre-check saw zero users, and confirms register_submit maps that to a
    403 with no session -- not a 500, and not a false "you're registered"."""
    client, storage = isolated_client(tmp_path, monkeypatch)
    assert storage.count_users() == 0

    def raise_integrity_error(*args, **kwargs):
        raise sqlite3.IntegrityError("UNIQUE constraint failed: users.username")

    monkeypatch.setattr(storage, "create_user", raise_integrity_error)

    resp = client.post(
        "/register", data={"username": "alice", "password": "whatever1"}, follow_redirects=False
    )

    assert resp.status_code == 403
    assert storage.count_users() == 0
    assert storage.get_user("alice") is None
    assert "session" not in resp.cookies


def test_register_get_shows_closed_message_when_already_registered(tmp_path, monkeypatch):
    """Renders the template's `closed` branch (not a redirect) -- a more
    informative dead end than silently bouncing to /login, and the reason
    that branch exists in register.html at all (it was previously dead
    code -- this route is the only thing that sets it)."""
    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("existing", "pbkdf2_sha256$260000$c2FsdA==$aGFzaA==")

    resp = client.get("/register")

    assert resp.status_code == 200
    assert "Registration is closed" in resp.text
    assert 'action="/register"' not in resp.text  # the form itself must not render


def test_login_wrong_password_rejected(tmp_path, monkeypatch):
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))

    resp = client.post("/login", data={"username": "alice", "password": "wrong-password"})

    assert resp.status_code == 401
    assert "session" not in resp.cookies
    # Still logged out afterward -- a protected route confirms no session leaked through.
    protected = client.get("/api/status")
    assert protected.status_code == 401


def test_login_unknown_username_rejected(tmp_path, monkeypatch):
    client, storage = isolated_client(tmp_path, monkeypatch)

    resp = client.post("/login", data={"username": "nobody", "password": "whatever1"})

    assert resp.status_code == 401
    assert "session" not in resp.cookies


def test_login_correct_credentials_starts_session(tmp_path, monkeypatch):
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))

    resp = client.post(
        "/login", data={"username": "alice", "password": "correct-password"}, follow_redirects=False
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/app/name"
    assert client.get("/api/status").status_code == 200


def test_protected_page_without_session_redirects_to_login(tmp_path, monkeypatch):
    client, _ = isolated_client(tmp_path, monkeypatch)

    resp = client.get("/app/name", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_protected_history_page_without_session_redirects_to_login(tmp_path, monkeypatch):
    client, _ = isolated_client(tmp_path, monkeypatch)

    resp = client.get("/history", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_protected_api_route_without_session_returns_401(tmp_path, monkeypatch):
    client, _ = isolated_client(tmp_path, monkeypatch)

    resp = client.get("/api/status")

    assert resp.status_code == 401


def test_landing_page_reachable_with_zero_session(tmp_path, monkeypatch):
    client, _ = isolated_client(tmp_path, monkeypatch)

    resp = client.get("/")

    assert resp.status_code == 200


def test_logout_clears_session(tmp_path, monkeypatch):
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))
    client.post("/login", data={"username": "alice", "password": "correct-password"})
    assert client.get("/api/status").status_code == 200

    logout_resp = client.post("/logout", follow_redirects=False)
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/"

    # A protected page now redirects to /login again, same as a client that
    # never logged in.
    resp = client.get("/app/name", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_websocket_rejected_without_session(tmp_path, monkeypatch):
    client, _ = isolated_client(tmp_path, monkeypatch)

    try:
        with client.websocket_connect("/ws"):
            raise AssertionError("expected the handshake to be rejected")
    except WebSocketDisconnect as e:
        assert e.code == 4401


def test_websocket_accepted_with_session(tmp_path, monkeypatch):
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))
    client.post("/login", data={"username": "alice", "password": "correct-password"})

    with client.websocket_connect("/ws") as ws:
        # No message expected immediately; just confirms the handshake
        # itself succeeded (didn't raise WebSocketDisconnect(4401)).
        ws.close()
