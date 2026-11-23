"""Re-download MP3s for songs already recorded as downloaded, then the queue.

Use case: the files (e.g. on an SD card) were lost but the database still
remembers them. Two phases:

1. RESTORE -- for every `downloaded` row with success=1, fetch the MP3 into
   the download dir. This uses YouTubeDownloader directly, which never
   touches the database, so existing history rows are left exactly as they
   are (no new rows, no timestamp or file_path changes). Files that already
   exist are skipped, so the script is safe to stop and re-run.
2. QUEUE -- download whatever is still in the library queue through the
   app's normal path (run_download_task): each outcome is recorded in
   `downloaded`, removed from the queue, and pushed to Fly if sync is
   configured.

Unavailable videos are skipped and listed in a report at the end.

Usage (from the project root, venv active):
    python scripts/restore_downloads.py --dry-run
    python scripts/restore_downloads.py --limit 3 --phase restore
    python scripts/restore_downloads.py                # everything
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.download_orchestrator import run_download_task  # noqa: E402
from app.services.downloader import YouTubeDownloader  # noqa: E402
from app.storage.storage import Storage  # noqa: E402


class _NullManager:
    """Stand-in for the WebSocket ConnectionManager (no clients here)."""

    def broadcast_threadsafe(self, *_a, **_kw):
        pass


def _expected_path(dl: YouTubeDownloader, info: dict) -> Path:
    # Mirrors the filename logic in YouTubeDownloader.download_audio.
    from app.utils import sanitize_filename

    vid = info.get("video_id") or ""
    part = sanitize_filename(f"{info['channel']} - {info['title']}")
    return dl.download_dir / (f"{part} [{vid}].mp3" if vid else f"{part}.mp3")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["restore", "queue", "all"], default="all")
    ap.add_argument("--limit", type=int, help="only process the first N items per phase")
    ap.add_argument("--dry-run", action="store_true", help="print counts only, download nothing")
    ap.add_argument("--report", default="restore_report.txt")
    args = ap.parse_args()

    storage = Storage()
    config = storage.load_config()
    dl = YouTubeDownloader(download_dir=config["download_dir"], audio_quality=config["audio_quality"])

    history = [r for r in storage.load_downloaded() if r["success"]]
    queue = storage.load_library()
    todo = [r for r in history if not _expected_path(dl, r).exists()]

    print(f"History (success): {len(history)}  | missing on disk: {len(todo)}")
    print(f"Queue: {len(queue)}")
    if args.dry_run:
        for r in todo[:5]:
            print("  e.g.", r["channel"], "-", r["title"])
        return 0

    failed: list[str] = []

    if args.phase in ("restore", "all"):
        batch = todo[: args.limit] if args.limit else todo
        for i, row in enumerate(batch, 1):
            print(f"[{i}/{len(batch)}] {row['title']}")
            # Read-only w.r.t. the DB: download_audio only writes the file.
            if not dl.download_audio(dict(row)):
                failed.append(f"{row['video_id']}  {row['channel']} - {row['title']}")

    if args.phase in ("queue", "all") and queue:
        ids = [q["video_id"] for q in queue][: args.limit] if args.limit else None
        import asyncio

        run_download_task(storage, _NullManager(), ids, asyncio.new_event_loop())
        # Items that failed stay recorded as success=0 rows; list them.
        for q in queue:
            if not storage.is_downloaded(q["video_id"]):
                failed.append(f"{q['video_id']}  {q['channel']} - {q['title']}")

    Path(args.report).write_text("\n".join(failed) + "\n", encoding="utf-8")
    print(f"\nDone. Skipped/failed: {len(failed)} (listed in {args.report})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
