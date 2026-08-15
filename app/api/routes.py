"""API routes for YouTube downloader."""
import asyncio
import logging
import threading
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.services.downloader import YouTubeDownloader
from app.services.search import YouTubeSearcher
from app.storage.storage import Storage
from app.utils import validate_download_dir
from app.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()
storage = Storage()
searcher = YouTubeSearcher()

# Guards against two /api/download requests running concurrently: without
# this, two overlapping background tasks can both pass download_audio()'s
# "does the file already exist" check before either has written anything,
# then both invoke yt-dlp against the *same* output path at the same time.
_download_lock = threading.Lock()
_download_in_progress = False

AudioQuality = Literal["128", "192", "256", "320"]


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=15, ge=1, le=100)


class URLRequest(BaseModel):
    url: str


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
    """Add video to library."""
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
async def get_downloaded() -> dict:
    """Get download history."""
    downloaded = storage.load_downloaded()
    return {"downloaded": downloaded}


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
    """Background task to download videos.

    Runs in a threadpool worker (FastAPI's BackgroundTasks), so progress and
    completion events are bridged onto the main event loop via `loop` to
    reach WebSocket clients.

    Caller (start_download) is responsible for holding _download_lock for
    the duration of this function -- see the comment there.
    """
    global _download_in_progress
    try:
        library = storage.load_library()

        # Filter by video_ids if provided
        if video_ids:
            library = [v for v in library if v['video_id'] in video_ids]

        if not library:
            return

        config = storage.load_config()

        def on_progress(video_id: str, percent: float):
            manager.broadcast_threadsafe({"type": "progress", "video_id": video_id, "percent": percent}, loop)

        downloader = YouTubeDownloader(
            download_dir=config['download_dir'],
            audio_quality=config['audio_quality'],
            progress_callback=on_progress,
        )

        # Download each video individually and update queue immediately
        for video_info in library:
            try:
                file_path = downloader.download_audio(video_info)
            except Exception:
                logger.exception("Unexpected error downloading %s", video_info.get('video_id'))
                file_path = None

            # Record the outcome (success *or* failure) before removing from
            # the queue, not after: these are two separate SQLite writes, and
            # if the process died between them in the old remove-then-record
            # order, a completed download could vanish from both tables. The
            # failure record also means a failed video is no longer silently
            # discarded -- it's queryable via /api/downloaded and, because
            # is_downloaded() only matches success=1 rows, still re-queueable.
            result = {
                **video_info,
                'success': bool(file_path),
                'file_path': file_path,
            }
            storage.add_to_downloaded(result)
            storage.remove_from_library(video_info['video_id'])

            if file_path:
                manager.broadcast_threadsafe(
                    {"type": "download_complete", "video_id": video_info['video_id'], "success": True}, loop
                )
            else:
                logger.warning("Download failed for %s (%s)", video_info.get('title'), video_info.get('video_id'))
                manager.broadcast_threadsafe(
                    {"type": "download_complete", "video_id": video_info['video_id'], "success": False}, loop
                )
    finally:
        with _download_lock:
            _download_in_progress = False


@router.post("/api/download")
async def start_download(background_tasks: BackgroundTasks, video_ids: list[str] | None = None) -> dict:
    """Start downloading library (or specific videos)."""
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

    # Start download in background, passing the current event loop so the
    # worker thread can broadcast progress back to WebSocket clients.
    loop = asyncio.get_running_loop()
    background_tasks.add_task(download_task, video_ids, loop)

    count = len(video_ids) if video_ids else len(library)

    return {
        "message": f"Started downloading {count} videos",
        "count": count
    }
