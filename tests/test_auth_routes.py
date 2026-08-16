"""HTTP-level tests for session-cookie auth routes (docs/15).

Each test gets its own TestClient (own cookie jar) plus an isolated Storage
pointed at tmp_path, monkeypatched onto app.main.auth_storage -- same
per-test isolation as tests/test_api_routes.py's `isolated_storage`, but a
fresh client per test too here, since a shared module-level client would
leak session cookies between tests the way test_api_routes.py's stateless
routes never had to worry about.
"""
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import main
from app.main import app
from app.storage.storage import Storage


def isolated_client(tmp_path, monkeypatch):
    storage = Storage(str(tmp_path))
    monkeypatch.setattr(main, "auth_storage", storage)
    # See tests/conftest.py's log_in_test_client for why these are reset per test.
    monkeypatch.setattr(main, "_failed_login_attempts", {})
    monkeypatch.setattr(main, "_registration_closed_cache", False)
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
    """The atomic create_user_if_first backstop (docs/16, 16-1) end-to-end:
    it returns False when another request won the race and already created
    the account, even though *this* request's caller-side view still looked
    open. Confirms register_submit maps that to a 403 with no session --
    not a 500, and not a false "you're registered"."""
    client, storage = isolated_client(tmp_path, monkeypatch)
    assert storage.count_users() == 0

    monkeypatch.setattr(storage, "create_user_if_first", lambda *a, **k: False)

    resp = client.post(
        "/register", data={"username": "alice", "password": "whatever1"}, follow_redirects=False
    )

    assert resp.status_code == 403
    assert storage.count_users() == 0
    assert storage.get_user("alice") is None
    assert "session" not in resp.cookies


def test_register_concurrent_different_usernames_only_one_wins(tmp_path, monkeypatch):
    """The actual bug docs/16's 16-1 describes: two concurrent registration
    requests for two *different* usernames used to both be able to pass a
    separate "count_users() == 0" check before either committed, since
    the old create_user()'s UNIQUE constraint only rejects a collision on
    the *same* username. create_user_if_first does the count-check and the
    insert under one lock acquisition instead, so only one of two
    concurrently-issued requests -- run here via a thread pool to actually
    race them -- ends up creating an account."""
    import concurrent.futures

    from app.storage.storage import Storage

    isolated_client(tmp_path, monkeypatch)  # just to get an isolated auth_storage dir
    storage = Storage(str(tmp_path / "_race"))
    monkeypatch.setattr(main, "auth_storage", storage)

    def register(username):
        return storage.create_user_if_first(username, "pbkdf2_sha256$260000$c2FsdA==$aGFzaA==")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, ["alice", "mallory"]))

    assert sorted(results) == [False, True]
    assert storage.count_users() == 1


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


def test_register_rejects_empty_username_or_password(tmp_path, monkeypatch):
    """docs/16, 16-13: empty-credential registration must be refused, not
    silently create an account with a blank username/password, and not a
    500. Truly-empty form fields never reach register_submit at all --
    FastAPI's own Form(...) validation rejects them with a 422 first (a
    genuinely absent value and an empty string are indistinguishable to
    it here); a whitespace-only username *does* reach register_submit's
    own `username.strip()` check, which is exercised below."""
    client, storage = isolated_client(tmp_path, monkeypatch)

    resp = client.post("/register", follow_redirects=False)  # no username/password at all
    assert resp.status_code == 422
    assert storage.count_users() == 0
    assert "session" not in resp.cookies

    whitespace_resp = client.post(
        "/register", data={"username": "   ", "password": "irrelevant"}, follow_redirects=False
    )
    assert whitespace_resp.status_code == 400
    assert "required" in whitespace_resp.text
    assert storage.count_users() == 0
    assert "session" not in whitespace_resp.cookies


def test_register_rejects_password_shorter_than_minimum(tmp_path, monkeypatch):
    """docs/16, 16-9: server-side minimum password length -- the real
    security boundary, same pattern as the registration-closed check
    (client-side validation, if any, is not trustworthy on its own)."""
    client, storage = isolated_client(tmp_path, monkeypatch)

    resp = client.post(
        "/register", data={"username": "alice", "password": "short"}, follow_redirects=False
    )

    assert resp.status_code == 400
    assert "at least" in resp.text
    assert storage.count_users() == 0
    assert "session" not in resp.cookies


def test_register_get_redirects_when_already_authenticated(tmp_path, monkeypatch):
    """docs/16, 16-13: a logged-in visitor hitting GET /register (e.g. an
    old bookmark/back-button) is bounced to the app, not shown a form that
    would 403 on submit anyway."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))
    client.post("/login", data={"username": "alice", "password": "correct-password"})

    resp = client.get("/register", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/app/name"


def test_login_get_redirects_when_already_authenticated(tmp_path, monkeypatch):
    """docs/16, 16-13: a logged-in visitor hitting GET /login is bounced
    straight to the app instead of being shown a login form again."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))
    client.post("/login", data={"username": "alice", "password": "correct-password"})

    resp = client.get("/login", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/app/name"


def test_login_open_redirect_next_falls_back_to_default(tmp_path, monkeypatch):
    """docs/16, 16-13: `next` must be validated as a same-app relative path
    (_safe_next_path in app/main.py) -- a protocol-relative or absolute
    `next` pointing off-site must never be honored, even on a successful
    login."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))

    for evil_next in ("//evil.example.com", "https://evil.example.com/phish", "http://evil.example.com"):
        resp = client.post(
            "/login",
            data={"username": "alice", "password": "correct-password", "next": evil_next},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/app/name"
        client.post("/logout")


def test_login_open_redirect_allows_safe_relative_next(tmp_path, monkeypatch):
    """The other half of 16-13's open-redirect coverage: a genuine
    same-app relative path must still work, so the fix isn't just
    "always ignore next"."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))

    resp = client.post(
        "/login",
        data={"username": "alice", "password": "correct-password", "next": "/history"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/history"


def test_login_rate_limit_blocks_rapid_repeated_failures(tmp_path, monkeypatch):
    """docs/16, 16-2: repeated failed logins for the same username get
    rate-limited (429) rather than allowed at unlimited speed."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))

    first = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert first.status_code == 401

    second = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert second.status_code == 429

    # Even the *correct* password is refused while the cooldown is active --
    # this limits attempt rate, not just wrong-password attempts.
    third = client.post("/login", data={"username": "alice", "password": "correct-password"})
    assert third.status_code == 429
    assert "session" not in third.cookies


def test_login_rate_limit_is_per_username(tmp_path, monkeypatch):
    """A cooldown on one username must not lock out a login attempt for a
    different one."""
    from app.passwords import hash_password

    client, storage = isolated_client(tmp_path, monkeypatch)
    storage.create_user("alice", hash_password("correct-password"))
    storage.create_user("bob", hash_password("bobs-password"))

    client.post("/login", data={"username": "alice", "password": "wrong"})

    resp = client.post("/login", data={"username": "bob", "password": "bobs-password"}, follow_redirects=False)
    assert resp.status_code == 303


def test_registration_open_caches_once_closed(tmp_path, monkeypatch):
    """docs/16, 16-16: once registration_open() observes an account, it
    must never query storage again -- registration can only ever go from
    open to closed once, for the process's whole lifetime."""
    client, storage = isolated_client(tmp_path, monkeypatch)

    assert main._registration_open() is True

    storage.create_user("alice", "pbkdf2_sha256$260000$c2FsdA==$aGFzaA==")
    assert main._registration_open() is False
    assert main._registration_closed_cache is True

    # Even if storage were to (impossibly) report zero users again, the
    # cached answer must not flip back open.
    monkeypatch.setattr(storage, "count_users", lambda: 0)
    assert main._registration_open() is False


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
