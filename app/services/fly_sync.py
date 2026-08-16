"""Sync mechanism between this local instance and a Fly-hosted deployment.

Local-only by design (gated on `app.utils.IS_PRODUCTION` being False in
every caller -- see app/api/routes.py's /api/sync/pull and /api/sync/status,
and app/services/download_orchestrator.py's push hook): the Fly deployment
never talks to itself this way, it only ever receives calls made *by* a
local instance.

Why this exists at all: the Fly deployment and any locally-run instance
each have their own, completely separate SQLite database (see README.md's
"local vs Fly" section). Something queued via the Fly-hosted web app or
Chrome extension is invisible to a local instance until pulled; a download
that actually happens locally is invisible to Fly until pushed. This module
is both directions of that bridge:

- pull_from_fly(): fetch Fly's current library queue and land anything not
  already known locally into the local queue (storage.add_to_library, same
  as any other queue-add -- no auto-download).
- push_download_outcome(): after a real local download finishes (success or
  failure), tell Fly about it (POST /api/downloaded/record) and remove the
  item from Fly's queue if it's there (DELETE /api/library/{video_id}).

Configured entirely via environment variables (FLY_SYNC_URL,
FLY_SYNC_USERNAME, FLY_SYNC_PASSWORD), read at runtime only -- same trust
model as SECRET_KEY (see app/main.py): never stored in the DB, never
committed. If any of the three is unset, sync is simply unavailable --
is_configured() returns False, no error, no crash.
"""
import logging
import os

import httpx

from app.storage.storage import Storage

logger = logging.getLogger(__name__)

# Generous but bounded -- these calls cross the network to a real (free-
# trial) Fly app that can be cold-starting; long enough to tolerate that,
# short enough that a hung remote can't wedge a caller forever.
_TIMEOUT_SECONDS = 30.0


class FlySyncError(Exception):
    """Talking to the remote Fly app failed: not configured, bad
    credentials, network error, or an unexpected response. pull_from_fly
    raises this so /api/sync/pull can surface a clear error to whoever
    triggered it; push_download_outcome catches it internally instead
    (push is best-effort, see its docstring)."""


def _fly_sync_url() -> str | None:
    url = os.environ.get("FLY_SYNC_URL")
    return url.rstrip("/") if url else None


def _fly_sync_username() -> str | None:
    return os.environ.get("FLY_SYNC_USERNAME") or None


def _fly_sync_password() -> str | None:
    return os.environ.get("FLY_SYNC_PASSWORD") or None


def is_configured() -> bool:
    """True only if FLY_SYNC_URL, FLY_SYNC_USERNAME, and FLY_SYNC_PASSWORD
    are all set. Sync is entirely opt-in via this env-var config -- someone
    not using Fly at all sees no behavior change anywhere."""
    return bool(_fly_sync_url() and _fly_sync_username() and _fly_sync_password())


def _login(client: httpx.Client, base_url: str, username: str, password: str) -> None:
    """POST /login on the remote Fly app and capture its session cookie
    into `client`'s cookie jar (httpx.Client persists cookies across calls
    made with it) for the calls that follow. Raises FlySyncError on any
    failure -- wrong credentials, the app down, or a network error.

    login_submit (app/main.py) responds 401 (form re-rendered with an
    error) on bad credentials and a 303 redirect on success -- httpx
    doesn't follow redirects by default, so success here is "303 seen",
    not "200 after following it".
    """
    try:
        resp = client.post(f"{base_url}/login", data={"username": username, "password": password})
    except httpx.HTTPError as e:
        raise FlySyncError(f"Could not reach {base_url}: {e}") from e
    if resp.status_code not in (200, 303):
        raise FlySyncError(f"Login to {base_url} failed (status {resp.status_code})")


def pull_from_fly(storage: Storage) -> dict:
    """Fetch the remote Fly app's library queue and add anything not
    already known locally -- checked via storage.get_item_status, which
    covers both "already queued locally" and "already downloaded
    locally" -- into the local queue via storage.add_to_library, exactly
    like any other queue-add. Never triggers a download.

    Returns {"pulled": n, "skipped": n}: `skipped` counts remote items
    already known locally, so calling this repeatedly is a safe no-op for
    them (running it twice in a row pulls 0 the second time).

    Raises FlySyncError if sync isn't configured or any remote call fails.
    """
    base_url = _fly_sync_url()
    username = _fly_sync_username()
    password = _fly_sync_password()
    if not (base_url and username and password):
        raise FlySyncError(
            "Fly sync is not configured (FLY_SYNC_URL/FLY_SYNC_USERNAME/FLY_SYNC_PASSWORD)"
        )

    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        _login(client, base_url, username, password)
        try:
            resp = client.get(f"{base_url}/api/library")
        except httpx.HTTPError as e:
            raise FlySyncError(f"Could not fetch remote library from {base_url}: {e}") from e
        if resp.status_code != 200:
            raise FlySyncError(f"Fetching remote library failed (status {resp.status_code})")
        remote_library = resp.json().get("library", [])

    pulled = 0
    skipped = 0
    for item in remote_library:
        video_id = item.get("video_id")
        if not video_id:
            continue
        if storage.get_item_status(video_id) != "new":
            skipped += 1
            continue
        storage.add_to_library({
            "video_id": video_id,
            "title": item["title"],
            "channel": item["channel"],
            "duration": item["duration"],
            "url": item["url"],
            "thumbnail": item["thumbnail"],
        })
        pulled += 1

    return {"pulled": pulled, "skipped": skipped}


def push_download_outcome(result: dict) -> None:
    """Best-effort push of one completed local download's outcome to the
    remote Fly app -- a no-op if sync isn't configured. Called from
    app/services/download_orchestrator.py for every real local download,
    success or failure, regardless of whether that item was originally
    pulled from Fly (simplest consistent rule, doesn't need per-item
    provenance tracking).

    Never raises: this must not block or fail the local download it
    follows, which has already succeeded or failed on its own merits by
    the time this runs. Any failure here (bad/expired remote credentials,
    Fly down, network blip) is logged and swallowed.

    `result` is the same dict run_download_task already builds for
    storage.add_to_downloaded -- must contain video_id/title/channel/
    duration/url/thumbnail/success, and may contain file_path.
    """
    base_url = _fly_sync_url()
    username = _fly_sync_username()
    password = _fly_sync_password()
    if not (base_url and username and password):
        return

    video_id = result["video_id"]
    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            _login(client, base_url, username, password)

            record_resp = client.post(
                f"{base_url}/api/downloaded/record",
                json={
                    "video_id": video_id,
                    "title": result["title"],
                    "channel": result["channel"],
                    "duration": result["duration"],
                    "url": result["url"],
                    "thumbnail": result["thumbnail"],
                    "success": bool(result.get("success")),
                    "file_path": result.get("file_path"),
                },
            )
            if record_resp.status_code != 200:
                logger.warning(
                    "Fly sync: recording download outcome for %s failed (status %s)",
                    video_id, record_resp.status_code,
                )
                return

            # Idempotent no-op if the item was never in Fly's library (or
            # was already removed) -- app/api/routes.py's
            # remove_from_library is a plain DELETE either way.
            delete_resp = client.delete(f"{base_url}/api/library/{video_id}")
            if delete_resp.status_code != 200:
                logger.warning(
                    "Fly sync: removing %s from the remote library failed (status %s)",
                    video_id, delete_resp.status_code,
                )
    except FlySyncError as e:
        logger.warning("Fly sync push for %s failed: %s", video_id, e)
    except httpx.HTTPError as e:
        logger.warning("Fly sync push for %s failed: %s", video_id, e)
    except Exception:
        logger.exception("Fly sync push for %s failed unexpectedly", video_id)
