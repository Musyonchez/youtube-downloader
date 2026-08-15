"""Optional HTTP Basic Auth gate.

This app was designed with no authentication at all, on the assumption
it's only ever reachable on a trusted LAN (see docs/09's audit -- that was
an explicit, reviewed decision). Deploying it publicly (docs/14) changes
that assumption, so this middleware exists specifically for that case: it
only activates when APP_USERNAME/APP_PASSWORD are both set in the
environment. Local/LAN/dev use is unaffected -- no env vars, no auth
prompt, exactly the zero-config experience the app always had.

Pure ASGI middleware (not Starlette's BaseHTTPMiddleware) so it can gate
WebSocket handshakes the same way it gates HTTP requests -- a
BaseHTTPMiddleware subclass only sees HTTP scopes.
"""
import base64
import binascii
import os
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send

# Fly's health check hits this with no credentials -- must stay open, or
# the app never becomes healthy and Fly kills the deploy.
_EXEMPT_PATHS = {"/health"}


class BasicAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self._username = os.environ.get("APP_USERNAME")
        self._password = os.environ.get("APP_PASSWORD")
        self.enabled = bool(self._username and self._password)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope.get("path") in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        if self._is_authorized(headers.get(b"authorization")):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            # No standard way to send a 401 during a WS handshake; closing
            # with a distinct (non-1000) code is the closest equivalent.
            await send({"type": "websocket.close", "code": 4401})
            return

        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"www-authenticate", b'Basic realm="YouTube MP3 Downloader"'),
                (b"content-type", b"text/plain"),
            ],
        })
        await send({"type": "http.response.body", "body": b"Authentication required"})

    def _is_authorized(self, auth_header: bytes | None) -> bool:
        if not auth_header or not auth_header.startswith(b"Basic "):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        username, _, password = decoded.partition(":")
        # compare_digest is timing-safe; both sides must be str (or both
        # bytes) of matching type, which is already the case here.
        assert self._username is not None and self._password is not None  # enabled implies both set
        return secrets.compare_digest(username, self._username) and secrets.compare_digest(password, self._password)
