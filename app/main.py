#!/usr/bin/env python3
"""FastAPI web application for YouTube MP3 downloader."""
import logging
import os
import secrets
import time
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router
from app.api.routes import storage as auth_storage
from app.passwords import hash_password, verify_password
from app.session_auth import SessionAuthMiddleware
from app.ws_manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube MP3 Downloader",
    description="Web-based YouTube audio downloader with thumbnail preview",
    version="2.0.0"
)

# Auth routes below reuse app/api/routes.py's module-level `storage`
# instance (docs/16, 16-6) rather than constructing a second, independent
# Storage/Database -- both used to point at the same on-disk `data/`
# directory, so two live instances meant two separate sqlite3 connections
# open against the same file for no benefit, plus config/library/downloaded
# state read through one instance could lag what the other just wrote.
# Tests still isolate this from routes.storage independently by
# monkeypatching each module's own reference (see tests/conftest.py and
# tests/test_api_routes.py) -- that's a test-only concern; in the running
# app there is exactly one Storage instance.

# Minimum wait between failed login attempts for a given username, doubling
# up to a cap -- see login_submit (docs/16, 16-2). Single-account app, so a
# per-username in-process counter is enough; no need for a new dependency.
_LOGIN_COOLDOWN_BASE_SECONDS = 1.0
_LOGIN_COOLDOWN_MAX_SECONDS = 30.0
_failed_login_attempts: dict[str, tuple[int, float]] = {}

# SECRET_KEY signs the session cookie (itsdangerous, via Starlette's
# SessionMiddleware) -- treat it like any other credential. Read from the
# environment so it survives process restarts in production (set as a Fly
# secret, see docs/14); if it's unset, generate a random one at startup so
# local `python -m app.main` and pytest still work with zero config, same
# zero-config bias as the old Basic Auth gate. The tradeoff: sessions don't
# survive a restart with a generated key -- fine for local dev, and fine in
# prod *only* as long as the Fly secret is actually set (it must be).
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning(
        "SECRET_KEY not set -- generated a random one for this process. "
        "Sessions will not survive a restart. Set SECRET_KEY as a persistent "
        "secret in production (see docs/14-deployment.md)."
    )

# Whether this process is a real deploy (Secure cookies required) or local/
# LAN dev (plain HTTP, so a Secure cookie would never come back and login
# would silently break). Previously this was inferred from "is SECRET_KEY
# set", which conflates two unrelated things -- SECRET_KEY can legitimately
# be set locally too (e.g. to test session persistence across restarts),
# which would have wrongly forced Secure cookies over plain HTTP (docs/16,
# 16-7). FLY_APP_NAME is set automatically by the Fly.io runtime for every
# deployed app, so it's a reliable, purpose-built signal instead; ENVIRONMENT
# is an explicit escape hatch for any other real deploy target.
IS_PRODUCTION = bool(os.environ.get("FLY_APP_NAME") or os.environ.get("ENVIRONMENT") == "production")

# Middleware order matters and is easy to get backwards silently (see
# app/session_auth.py's docstring): Starlette runs the *last*-added
# middleware *first* (outermost), so SessionMiddleware -- which must
# populate request.session before SessionAuthMiddleware reads it -- is
# added last here, even though it's conceptually "first" in the request
# flow. Verified empirically with a throwaway script during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionAuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    # Secure cookie only in a real deploy (see IS_PRODUCTION above) --
    # local/LAN use is plain HTTP, and a Secure cookie would never be sent
    # back over it, silently breaking login.
    https_only=IS_PRODUCTION,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router)

templates = Jinja2Templates(directory="templates")
# Computed fresh per-render (not baked in at startup) so a long-running
# process still shows the correct year in the footer on Dec 31 -> Jan 1.
templates.env.globals["current_year"] = lambda: datetime.now().year
# Makes the logged-in username (or None) available to every template via
# {{ current_user(request) }} without editing every route handler's context
# dict -- `request` is already in context on every TemplateResponse call.
templates.env.globals["current_user"] = lambda request: request.session.get("user")
# Drives the navbar's Register link (docs/15): only shown while no account
# exists yet. Re-checks storage on every render rather than caching, since
# it must flip to hidden the instant the first account is created.
templates.env.globals["registration_open"] = lambda: auth_storage.count_users() == 0


def _safe_next_path(next_path: str | None) -> str:
    """Validate a `next` redirect target is a same-app relative path, not
    an open redirect to an attacker-controlled host. Anything that doesn't
    look like a plain relative path (empty, protocol-relative `//evil.com`,
    absolute `https://evil.com`, or containing a netloc) falls back to the
    app's own default landing spot."""
    if not next_path or not next_path.startswith("/") or next_path.startswith("//"):
        return "/app/name"
    if urlsplit(next_path).netloc:
        return "/app/name"
    return next_path


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint broadcasting real-time download progress.

    Download progress originates in services/downloader.py's yt-dlp progress
    hook, which runs in a background-task worker thread; api/routes.py
    bridges that into this connection manager via broadcast_threadsafe.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the landing page."""
    return templates.TemplateResponse(request, "index.html")


MODE_LABELS = {"name": "Name", "playlist": "Playlist", "url": "URL"}


@app.get("/app/{mode}", response_class=HTMLResponse)
async def read_app(request: Request, mode: str):
    """Serve the app page with different search modes."""
    if mode not in MODE_LABELS:
        return HTMLResponse(content="<h1>Invalid mode</h1>", status_code=404)

    return templates.TemplateResponse(
        request,
        "app.html",
        {"mode": mode, "mode_label": MODE_LABELS[mode], "active_mode": mode, "show_settings": True},
    )


@app.get("/history", response_class=HTMLResponse)
async def read_history(request: Request):
    """Serve the download history page (docs/09, AUD-26)."""
    return templates.TemplateResponse(request, "history.html", {"active_mode": "history"})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}


# ---------------------------------------------------------------------------
# Auth pages (docs/15): session-cookie login/register/logout. Page-rendering
# routes like the ones above, not JSON API routes, so these live here rather
# than in app/api/routes.py -- matches how read_root/read_app/read_history
# are already structured.
# ---------------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str | None = None):
    """Render the login page. Already-logged-in visitors are bounced
    straight to the app -- no reason to show them a login form."""
    if request.session.get("user"):
        return RedirectResponse("/app/name", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"next": next or ""})


def _login_cooldown_remaining(username: str) -> float:
    """Seconds a client must still wait before this username can attempt
    another login -- 0 if it's free to try now. Doubles per consecutive
    failure (1s, 2s, 4s, ... capped at _LOGIN_COOLDOWN_MAX_SECONDS), reset
    on any successful login. In-process only (docs/16, 16-2): good enough
    for this app's single-account scope (a distributed store would only
    matter across multiple app instances, which this deploy doesn't have),
    and avoids pulling in a new dependency like slowapi for one counter."""
    entry = _failed_login_attempts.get(username)
    if entry is None:
        return 0.0
    failures, last_attempt_at = entry
    wait = min(_LOGIN_COOLDOWN_BASE_SECONDS * (2 ** (failures - 1)), _LOGIN_COOLDOWN_MAX_SECONDS)
    remaining = wait - (time.monotonic() - last_attempt_at)
    return float(max(0.0, remaining))


def _record_login_failure(username: str) -> None:
    failures, _ = _failed_login_attempts.get(username, (0, 0.0))
    _failed_login_attempts[username] = (failures + 1, time.monotonic())


def _clear_login_failures(username: str) -> None:
    _failed_login_attempts.pop(username, None)


@app.post("/login")
async def login_submit(
    request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("")
):
    """Verify credentials and start a session. Wrong username/password
    re-renders the form with an error and a 401 status -- never a silent
    200 with no session set. Also enforced: a short, doubling cooldown per
    username after each failed attempt (docs/16, 16-2), so a brute-force
    script can't hammer the single account's password at network speed."""
    cooldown = _login_cooldown_remaining(username)
    if cooldown > 0:
        return templates.TemplateResponse(
            request, "login.html",
            {"next": next, "error": "Too many attempts. Please wait a moment and try again."},
            status_code=429,
        )

    user = auth_storage.get_user(username)
    if user is None or not verify_password(password, user["password_hash"]):
        _record_login_failure(username)
        return templates.TemplateResponse(
            request, "login.html",
            {"next": next, "error": "Incorrect username or password."},
            status_code=401,
        )

    _clear_login_failures(username)
    request.session["user"] = username
    return RedirectResponse(_safe_next_path(next), status_code=303)


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Render the register page -- showing the form only while registration
    is open (no account created yet), a "closed" message otherwise. This
    GET-time check is UX only; the real security boundary is the re-check
    in register_submit below."""
    if request.session.get("user"):
        return RedirectResponse("/app/name", status_code=303)
    closed = auth_storage.count_users() > 0
    return templates.TemplateResponse(request, "register.html", {"closed": closed})


_MIN_PASSWORD_LENGTH = 8


@app.post("/register")
async def register_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Create the sole account, if none exists yet. This is the actual
    security boundary (docs/15) -- re-checks count_users() == 0 itself
    rather than trusting that the GET page's check was honored, since this
    route can be hit directly (curl/devtools), bypassing the UI entirely.

    The count-check and the insert happen atomically in
    auth_storage.create_user_if_first (docs/16, 16-1) -- a plain
    "count_users() == 0, then create_user()" here would be two separate
    storage calls with a window between them where two concurrent requests
    for two *different* usernames could each see zero users and both go on
    to create an account; the username-collision case (same name twice) was
    the only thing the old IntegrityError backstop actually caught.
    """
    username = username.strip()
    if not username or not password:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Username and password are required."}, status_code=400,
        )

    if len(password) < _MIN_PASSWORD_LENGTH:
        return templates.TemplateResponse(
            request, "register.html",
            {"error": f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."},
            status_code=400,
        )

    created = auth_storage.create_user_if_first(username, hash_password(password))
    if not created:
        return HTMLResponse("<h1>Registration is closed.</h1>", status_code=403)

    request.session["user"] = username
    return RedirectResponse("/app/name", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    """Clear the session. POST-only (not a GET link) so logging out can't
    happen via link prefetching or CSRF-via-<img>/<a>."""
    request.session.clear()
    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import sys

    import uvicorn

    # Avoid UnicodeEncodeError when stdout isn't UTF-8 (e.g. redirected or
    # backgrounded on Windows, where the console falls back to cp1252).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("🚀 Starting YouTube MP3 Downloader...")
    print("📱 Open http://localhost:8000 in your browser")
    print("🌐 Or access from phone: http://<your-pc-ip>:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
