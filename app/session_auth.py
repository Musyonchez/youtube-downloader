"""Session-cookie auth gate, replacing app/auth.py's Basic Auth (docs/15).

Single-account app: whoever registers first (see the /register route in
app/main.py) becomes the account, then registration closes. This
middleware's only job is enforcing "no valid session -> no access" on
every request except the small allowlist below -- it does NOT touch
storage or verify credentials itself; that happens once, at login/register
time, in app/main.py's route handlers. This middleware only ever reads
`request.session.get("user")`, which Starlette's SessionMiddleware
populates (from a signed cookie) before this middleware runs.

Pure ASGI middleware (not Starlette's BaseHTTPMiddleware), same reasoning
as app/auth.py: it needs to gate the /ws WebSocket handshake too, which a
BaseHTTPMiddleware subclass never sees (it only sees HTTP scopes).

IMPORTANT ordering requirement: this middleware relies on
`scope["session"]` already being populated, which is SessionMiddleware's
job. Starlette runs middleware in *reverse* of registration order (the
last one added ends up outermost, i.e. runs first) -- so in app/main.py,
SessionMiddleware must be added with app.add_middleware() *after* this
one, so it ends up outermost and populates the session before this
middleware's __call__ runs. Verified empirically with a throwaway script
during development; getting this backwards fails silently (every request
just looks logged-out, no error) rather than raising, so it's easy to get
wrong without checking.
"""
from urllib.parse import quote

from starlette.types import ASGIApp, Receive, Scope, Send

# Always reachable, no session required. Exact-match paths, plus the
# /static/ prefix for CSS/JS/images.
_EXEMPT_PATHS = {"/", "/login", "/register", "/logout", "/health"}
_EXEMPT_PREFIXES = ("/static/",)

# Page routes: redirect to /login on failure (a redirect is useless to a
# fetch() call, but is exactly what a browser navigating to a protected
# page needs). Matched by exact path or prefix.
_PAGE_PREFIXES = ("/app/",)
_PAGE_EXACT = {"/history"}


def _is_exempt(path: str) -> bool:
    return path in _EXEMPT_PATHS or any(path.startswith(p) for p in _EXEMPT_PREFIXES)


def _is_page_route(path: str) -> bool:
    return path in _PAGE_EXACT or any(path.startswith(p) for p in _PAGE_PREFIXES)


class SessionAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if _is_exempt(path):
            await self.app(scope, receive, send)
            return

        # SessionMiddleware (registered after this one, so it runs first --
        # see module docstring) has already populated scope["session"] from
        # the signed cookie by the time we get here.
        session = scope.get("session") or {}
        if session.get("user"):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            # No standard way to send a 401 during a WS handshake; closing
            # with a distinct (non-1000) code is the closest equivalent --
            # mirrors app/auth.py's BasicAuthMiddleware exactly.
            await send({"type": "websocket.close", "code": 4401})
            return

        if _is_page_route(path):
            next_qs = quote(path, safe="")
            await send({
                "type": "http.response.start",
                "status": 303,
                "headers": [
                    (b"location", f"/login?next={next_qs}".encode("ascii")),
                    (b"content-type", b"text/plain"),
                ],
            })
            await send({"type": "http.response.body", "body": b"Redirecting to login"})
            return

        # Everything else protected (/api/*, /ws's HTTP-adjacent siblings if
        # any) gets a JSON 401 -- a redirect would be useless to fetch().
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": b'{"detail":"Authentication required"}'})
