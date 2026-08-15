"""Tests for app/auth.py's BasicAuthMiddleware.

Tested against a minimal throwaway Starlette app (not app.main) so env
vars can be varied freely without import-order issues -- app.main
constructs its middleware once at import time, which real request tests
against the full app can't easily un-configure per test case.
"""
import base64

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import BasicAuthMiddleware


def _basic_auth_header(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _make_client(monkeypatch, username=None, password=None):
    if username is not None:
        monkeypatch.setenv("APP_USERNAME", username)
    else:
        monkeypatch.delenv("APP_USERNAME", raising=False)
    if password is not None:
        monkeypatch.setenv("APP_PASSWORD", password)
    else:
        monkeypatch.delenv("APP_PASSWORD", raising=False)

    async def homepage(request):
        return PlainTextResponse("ok")

    async def health(request):
        return PlainTextResponse("healthy")

    async def ws_endpoint(websocket):
        await websocket.accept()
        await websocket.send_text("hi")
        await websocket.close()

    app = Starlette(routes=[
        Route("/", homepage),
        Route("/health", health),
        WebSocketRoute("/ws", ws_endpoint),
    ])
    app.add_middleware(BasicAuthMiddleware)
    return TestClient(app)


def test_disabled_when_env_vars_unset(monkeypatch):
    client = _make_client(monkeypatch)
    assert client.get("/").status_code == 200


def test_disabled_when_only_username_set(monkeypatch):
    # Both must be set to enable -- a half-configured deploy shouldn't
    # silently lock everyone out (or silently stay wide open either way,
    # but "only one var set" almost certainly means misconfiguration, and
    # failing open here matches this app's existing zero-config default).
    client = _make_client(monkeypatch, username="admin")
    assert client.get("/").status_code == 200


def test_rejects_missing_credentials_when_enabled(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Basic")


def test_rejects_wrong_password(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/", headers=_basic_auth_header("admin", "wrong"))
    assert resp.status_code == 401


def test_rejects_wrong_username(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/", headers=_basic_auth_header("someone-else", "secret"))
    assert resp.status_code == 401


def test_accepts_correct_credentials(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/", headers=_basic_auth_header("admin", "secret"))
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_health_endpoint_exempt_even_when_enabled(monkeypatch):
    """Fly's health check has no credentials -- must stay reachable, or
    the deploy never goes healthy and Fly kills it (see docs/14)."""
    client = _make_client(monkeypatch, username="admin", password="secret")
    assert client.get("/health").status_code == 200


def test_malformed_auth_header_rejected(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/", headers={"Authorization": "Basic not-valid-base64!!"})
    assert resp.status_code == 401


def test_non_basic_auth_scheme_rejected(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    resp = client.get("/", headers={"Authorization": "Bearer sometoken"})
    assert resp.status_code == 401


def test_websocket_rejected_without_credentials(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    try:
        with client.websocket_connect("/ws"):
            raise AssertionError("expected the handshake to be rejected")
    except WebSocketDisconnect as e:
        assert e.code == 4401


def test_websocket_accepted_with_credentials(monkeypatch):
    client = _make_client(monkeypatch, username="admin", password="secret")
    with client.websocket_connect("/ws", headers=_basic_auth_header("admin", "secret")) as ws:
        assert ws.receive_text() == "hi"


def test_websocket_open_when_disabled(monkeypatch):
    client = _make_client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_text() == "hi"
