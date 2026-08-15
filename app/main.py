#!/usr/bin/env python3
"""FastAPI web application for YouTube MP3 downloader."""
import logging
import os
import secrets
import sqlite3
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router
from app.passwords import hash_password, verify_password
from app.session_auth import SessionAuthMiddleware
from app.storage.storage import Storage
from app.ws_manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube MP3 Downloader",
    description="Web-based YouTube audio downloader with thumbnail preview",
    version="2.0.0"
)

# Own Storage instance for the auth routes below (app/api/routes.py has its
# own module-level `storage` for the library/download endpoints -- kept
# separate rather than importing that one, since tests isolate routes.py's
# storage independently and importing it here would couple the two).
auth_storage = Storage()

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
    # Secure cookie only when SECRET_KEY is explicitly set (i.e. a real
    # deploy, not local dev) -- local/LAN use is plain HTTP, and a Secure
    # cookie would never be sent back over it, silently breaking login.
    https_only=bool(os.environ.get("SECRET_KEY")),
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


@app.post("/login")
async def login_submit(
    request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("")
):
    """Verify credentials and start a session. Wrong username/password
    re-renders the form with an error and a 401 status -- never a silent
    200 with no session set."""
    user = auth_storage.get_user(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"next": next, "error": "Incorrect username or password."},
            status_code=401,
        )

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


@app.post("/register")
async def register_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Create the sole account, if none exists yet. This is the actual
    security boundary (docs/15) -- re-checks count_users() == 0 itself
    rather than trusting that the GET page's check was honored, since this
    route can be hit directly (curl/devtools), bypassing the UI entirely.
    Also guards the race where two requests both pass the count check
    before either commits: create_user's PRIMARY KEY constraint raises
    IntegrityError for the loser, which is treated the same as "registration
    already closed".
    """
    username = username.strip()
    if not username or not password:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Username and password are required."}, status_code=400,
        )

    if auth_storage.count_users() > 0:
        return HTMLResponse("<h1>Registration is closed.</h1>", status_code=403)

    try:
        auth_storage.create_user(username, hash_password(password))
    except sqlite3.IntegrityError:
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
