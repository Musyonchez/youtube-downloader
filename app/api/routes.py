"""API routes for YouTube downloader."""
import asyncio
import logging
import threading
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.download_orchestrator import run_download_task
from app.services.downloader import YouTubeDownloader
from app.services.search import YouTubeSearcher
from app.storage.storage import Storage
from app.utils import IS_PRODUCTION, validate_download_dir
from app.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()
storage = Storage()
searcher = YouTubeSearcher()

# Guards against two /api/download requests running concurrently: without
# this, two overlapping background tasks can both pass download_audio()'s
# "does the file already exist" check before either has written anything,
# then both invoke yt-dlp against the *same* output path at the same time.
#
# Deliberately threading.Lock, not asyncio.Lock (docs/16, 16-25 flagged
# this as worth a second look -- deferred, not fixed, for this reason):
# this lock is acquired both from start_download (an async route handler,
# running on the event loop thread) and from download_task (a plain sync
# function, which FastAPI's BackgroundTasks runs in a worker thread via
# anyio's threadpool) -- it genuinely crosses threads, so it has to be a
# real OS-level lock. asyncio.Lock is explicitly not thread-safe and would
# be actively wrong here, not just a style swap. The other half of that
# finding -- a blocking lock acquisition briefly stalling the event loop
# inside an async handler -- is real but negligible in practice: every
# critical section under this lock (and under db.Database._lock, same
# reasoning, also legitimately cross-thread) is a handful of attribute
# reads/writes with no I/O, sub-microsecond in practice, vs. the
# multi-second network/disk I/O everything else in this app already does.
_download_lock = threading.Lock()
_download_in_progress = False

AudioQuality = Literal["128", "192", "256", "320"]


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=15, ge=1, le=100)


class URLRequest(BaseModel):
    url: str


class StatusesRequest(BaseModel):
    video_ids: list[str] = Field(max_length=200)


class VideoItem(BaseModel):
    video_id: str
    title: str
    channel: str
    duration: str
    url: str
    thumbnail: str


class StatusResponse(BaseModel):
    library_count: int
    downloaded_count: int


class ConfigUpdate(BaseModel):
    """Partial config update -- only fields that are set get applied."""
    audio_quality: AudioQuality | None = None
    format: Literal["mp3"] | None = None
    download_dir: str | None = None


# API Endpoints

@router.get("/api/status")
async def get_status() -> StatusResponse:
    """Get current status (queue count, downloaded count)."""
    return StatusResponse(
        library_count=storage.count_library(),
        downloaded_count=storage.count_downloaded()
    )


@router.post("/api/search")
async def search_videos(request: SearchRequest) -> dict:
    """Search YouTube by query."""
    results = searcher.search_by_name(request.query, request.limit)

    # Batch status lookup: 2 queries total instead of up to 2 per result.
    statuses = storage.get_statuses([video['video_id'] for video in results])
    enhanced_results = [{**video, 'status': statuses[video['video_id']]} for video in results]

    return {"results": enhanced_results}


@router.post("/api/statuses")
async def get_video_statuses(request: StatusesRequest) -> dict:
    """Batch status lookup for arbitrary video IDs, no yt-dlp calls -- used by
    the extension's on-page thumbnail badges across regular YouTube browsing,
    where calling /api/video-info per thumbnail would be far too slow/heavy.
    """
    return {"statuses": storage.get_statuses(request.video_ids)}


@router.post("/api/video-info")
async def get_video_info(request: URLRequest) -> dict:
    """Get video info from URL."""
    is_valid, url_type = searcher.validate_url(request.url)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    if url_type == 'playlist':
        raise HTTPException(status_code=400, detail="Use /api/playlist-info for playlist URLs")

    video_info = searcher.get_video_info(request.url)

    if not video_info:
        raise HTTPException(status_code=404, detail="Could not fetch video information")

    status = storage.get_item_status(video_info['video_id'])

    return {
        **video_info,
        'status': status
    }


@router.post("/api/playlist-info")
async def get_playlist_info(request: URLRequest) -> dict:
    """Get playlist info from URL."""
    is_valid, url_type = searcher.validate_url(request.url)

    if not is_valid or url_type != 'playlist':
        raise HTTPException(status_code=400, detail="Invalid playlist URL")

    videos = searcher.get_playlist_videos(request.url)

    if not videos:
        raise HTTPException(status_code=404, detail="Could not fetch playlist")

    # Batch status lookup -- matters most here: playlists can be up to 1000
    # items, which used to mean up to 2000 sequential locked SQLite calls.
    statuses = storage.get_statuses([video['video_id'] for video in videos])

    new_count = 0
    queued_count = 0
    downloaded_count = 0

    enhanced_videos = []
    for video in videos:
        status = statuses[video['video_id']]
        enhanced_videos.append({
            **video,
            'status': status
        })

        if status == 'new':
            new_count += 1
        elif status == 'queued':
            queued_count += 1
        elif status == 'downloaded':
            downloaded_count += 1

    return {
        'videos': enhanced_videos,
        'summary': {
            'total': len(videos),
            'new': new_count,
            'queued': queued_count,
            'downloaded': downloaded_count
        }
    }


@router.get("/api/library")
async def get_library() -> dict:
    """Get library queue."""
    library = storage.load_library()
    return {"library": library}


@router.post("/api/library/add")
async def add_to_library(video: VideoItem) -> dict:
    """Add video to library.

    Unlike /api/video-info and /api/playlist-info, this route's `video.url`
    was never run through searcher.validate_url's host allowlist (docs/16,
    16-10) -- video_info/playlist-info are the normal path here (search
    result -> add to library), but this route can be hit directly with an
    arbitrary `url`, and download_orchestrator.py hands that URL straight
    to yt-dlp at download time. Low real-world severity now that every
    route requires a session (docs/15), but worth being consistent with
    the SSRF hardening already done on the sibling routes.
    """
    is_valid, _ = searcher.validate_url(video.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    video_dict = video.dict()

    # Check if already exists
    status = storage.get_item_status(video.video_id)

    if status == 'downloaded':
        raise HTTPException(status_code=400, detail="Video already downloaded")
    elif status == 'queued':
        raise HTTPException(status_code=400, detail="Video already in queue")

    storage.add_to_library(video_dict)

    return {"message": "Added to library", "video_id": video.video_id}


@router.delete("/api/library/{video_id}")
async def remove_from_library(video_id: str) -> dict:
    """Remove video from library."""
    storage.remove_from_library(video_id)
    return {"message": "Removed from library"}


@router.delete("/api/library")
async def clear_library() -> dict:
    """Clear entire library."""
    storage.clear_library()
    return {"message": "Library cleared"}


@router.get("/api/downloaded")
async def get_downloaded(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Get a page of download history, newest-first (docs/16, 16-8).

    The history table only ever grows (every attempt, success or failure,
    is kept permanently) -- previously this returned the *entire* table on
    every call, which meant every /history page load pulled progressively
    more data as history grew. `limit`/`offset` bound each request; `total`
    tells the caller how many more rows exist so it can page through the
    rest (see static/js/history.js's "Load more").
    """
    downloaded = storage.load_downloaded(limit=limit, offset=offset, descending=True)
    return {"downloaded": downloaded, "total": storage.count_downloaded()}


@router.get("/api/config")
async def get_config() -> dict:
    """Get configuration."""
    config = storage.load_config()
    return config


@router.post("/api/config")
async def update_config(config: ConfigUpdate) -> dict:
    """Update configuration. Only fields provided in the request are changed."""
    updates = config.dict(exclude_unset=True, exclude_none=True)

    if 'download_dir' in updates:
        try:
            validate_download_dir(updates['download_dir'])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    storage.update_config(**updates)
    return {"message": "Configuration updated"}


# Background task for downloading
def download_task(video_ids: list[str] | None, loop: asyncio.AbstractEventLoop):
    """Background-thread entrypoint for FastAPI's BackgroundTasks.

    The actual batch-download logic lives in
    app.services.download_orchestrator.run_download_task (kept in the
    services layer, not here -- see docs/09, AUD-18); this wrapper's only
    job is bridging that into the background-task API and releasing the
    concurrency guard (_download_lock, see start_download) once done,
    success or failure.
    """
    global _download_in_progress
    try:
        run_download_task(storage, manager, video_ids, loop, downloader_cls=YouTubeDownloader)
    finally:
        with _download_lock:
            _download_in_progress = False


@router.post("/api/download")
async def start_download(background_tasks: BackgroundTasks, video_ids: list[str] | None = None) -> dict:
    """Start downloading library (or specific videos).

    Refused entirely on the Fly.io deployment (IS_PRODUCTION) -- actual
    downloads spawn yt-dlp/ffmpeg processes and write real files, which
    burns through Fly's free-trial compute/bandwidth for no benefit: the
    hosted instance exists for browsing/queueing from anywhere (web app,
    Chrome extension), the real downloading is meant to happen on a
    locally-run instance instead, where it's free and has real disk to
    write to. Queueing (add-to-library) is untouched -- that's a cheap DB
    write, not the expensive part. Client-IP-based gating was considered
    and rejected: Fly proxies every request, so the app never sees a real
    client IP to check against, and IP-checking would also have broken
    downloads from other devices on the user's home LAN (this app's own
    "any device on your network" feature) if applied to the local
    deployment too. Environment-based gating gets the actual goal (no
    downloads on Fly, ever, regardless of who's asking) without that
    collateral damage.
    """
    if IS_PRODUCTION:
        raise HTTPException(
            status_code=403,
            detail=(
                "Downloads are disabled on the hosted deployment to avoid "
                "using up Fly.io's free-trial resources. Run this app "
                "locally (see README.md) to actually download."
            ),
        )

    global _download_in_progress

    library = storage.load_library()

    if not library:
        raise HTTPException(status_code=400, detail="Library is empty")

    # Reject a second concurrent download run rather than letting two
    # background tasks race on the same output file (see _download_lock).
    with _download_lock:
        if _download_in_progress:
            raise HTTPException(status_code=409, detail="A download is already in progress")
        _download_in_progress = True

    # download_task's own `finally` (below) is what normally releases the
    # guard -- but that only runs once the background task actually starts
    # executing. If anything between the `_download_in_progress = True`
    # above and a successful add_task() were to raise (docs/16, 16-25: a
    # theoretical path, not observed -- get_running_loop() can't fail
    # inside a running async route handler, and add_task() itself just
    # appends to a list), the guard would be stuck True forever with no
    # background task ever scheduled to release it, wedging every future
    # /api/download behind a 409 until the process restarts. Cheap
    # insurance either way: release it here too on that path, then
    # re-raise so the caller still sees a real error instead of a
    # misleading success.
    try:
        # Start download in background, passing the current event loop so
        # the worker thread can broadcast progress back to WebSocket clients.
        loop = asyncio.get_running_loop()
        background_tasks.add_task(download_task, video_ids, loop)
    except Exception:
        with _download_lock:
            _download_in_progress = False
        raise

    count = len(video_ids) if video_ids else len(library)

    return {
        "message": f"Started downloading {count} videos",
        "count": count
    }
