"""API routes for YouTube downloader."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from downloader import YouTubeDownloader
from search import YouTubeSearcher
from utils import Storage

router = APIRouter()
storage = Storage()
searcher = YouTubeSearcher()


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    limit: int = 15


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


# API Endpoints

@router.get("/api/status")
async def get_status() -> StatusResponse:
    """Get current status (queue count, downloaded count)."""
    library = storage.load_library()
    downloaded = storage.load_downloaded()

    return StatusResponse(
        library_count=len(library),
        downloaded_count=len(downloaded)
    )


@router.post("/api/search")
async def search_videos(request: SearchRequest) -> dict:
    """Search YouTube by query."""
    results = searcher.search_by_name(request.query, request.limit)

    # Add status to each result
    enhanced_results = []
    for video in results:
        status = storage.get_item_status(video['video_id'])
        enhanced_results.append({
            **video,
            'status': status
        })

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

    # Add status to each video
    new_count = 0
    queued_count = 0
    downloaded_count = 0

    enhanced_videos = []
    for video in videos:
        status = storage.get_item_status(video['video_id'])
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


@router.post("/api/library/add-multiple")
async def add_multiple_to_library(videos: list[VideoItem]) -> dict:
    """Add multiple videos to library."""
    added = 0
    skipped = 0

    for video in videos:
        video_dict = video.dict()
        status = storage.get_item_status(video.video_id)

        if status == 'new':
            storage.add_to_library(video_dict)
            added += 1
        else:
            skipped += 1

    return {
        "message": f"Added {added} videos, skipped {skipped}",
        "added": added,
        "skipped": skipped
    }


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
async def update_config(config: dict) -> dict:
    """Update configuration."""
    storage.update_config(**config)
    return {"message": "Configuration updated"}


# Background task for downloading
def download_task(video_ids: list[str] | None = None):
    """Background task to download videos."""
    library = storage.load_library()

    # Filter by video_ids if provided
    if video_ids:
        library = [v for v in library if v['video_id'] in video_ids]

    if not library:
        return

    config = storage.load_config()
    downloader = YouTubeDownloader(
        download_dir=config['download_dir'],
        audio_quality=config['audio_quality']
    )

    # Download each video individually and update queue immediately
    for video_info in library:
        file_path = downloader.download_audio(video_info)

        # Always remove from queue after attempting download
        storage.remove_from_library(video_info['video_id'])

        # Only add to downloaded history if successful
        if file_path:
            result = {
                **video_info,
                'success': True,
                'file_path': file_path
            }
            storage.add_to_downloaded(result)


@router.post("/api/download")
async def start_download(background_tasks: BackgroundTasks, video_ids: list[str] | None = None) -> dict:
    """Start downloading library (or specific videos)."""
    library = storage.load_library()

    if not library:
        raise HTTPException(status_code=400, detail="Library is empty")

    # Start download in background
    background_tasks.add_task(download_task, video_ids)

    count = len(video_ids) if video_ids else len(library)

    return {
        "message": f"Started downloading {count} videos",
        "count": count
    }
