"""Orchestrates downloading the library queue.

This is the actual batch-download business logic -- previously embedded
directly in app/api/routes.py's download_task, which made the API layer
(meant to be a thin HTTP adapter) the largest and most logic-heavy module
in the app (see docs/09, AUD-18). Moved here with dependencies passed in
explicitly rather than reached for as module globals, which also makes it
straightforward to unit test without monkeypatching another module.
"""
import asyncio
import logging

from app.services.downloader import YouTubeDownloader
from app.storage.storage import Storage
from app.ws_manager import ConnectionManager

logger = logging.getLogger(__name__)


def run_download_task(
    storage: Storage,
    manager: ConnectionManager,
    video_ids: list[str] | None,
    loop: asyncio.AbstractEventLoop,
    downloader_cls: type[YouTubeDownloader] = YouTubeDownloader,
) -> None:
    """Download every queued video (or just `video_ids` if given).

    Records each outcome (success *and* failure -- see docs/09, AUD-02/03)
    before removing the item from the queue, and broadcasts progress/
    completion over `manager`. Runs synchronously; callers running this in
    a background thread (see app/api/routes.py's start_download) are
    responsible for that, and for releasing any concurrency guard.
    """
    library = storage.load_library()

    if video_ids:
        library = [v for v in library if v['video_id'] in video_ids]

    if not library:
        return

    config = storage.load_config()

    def on_progress(video_id: str, percent: float):
        manager.broadcast_threadsafe({"type": "progress", "video_id": video_id, "percent": percent}, loop)

    downloader = downloader_cls(
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
