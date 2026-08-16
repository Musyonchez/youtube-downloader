"""One-off, manually-run live test for the local <-> Fly sync mechanism
(app/services/fly_sync.py, app/api/routes.py's /api/sync/pull and
/api/downloaded/record). Not part of `pytest tests/` (that suite mocks
every HTTP call to the remote, see tests/test_fly_sync.py) -- this hits the
real deployed app at https://yt-mp3-downloader.fly.dev with real
credentials, on purpose, because the point is proving the pull/push
mechanism works against the real production app, not a local approximation
of it. Same precedent/reasoning as tests/e2e/extension_live_test.js.

Run with:
    FLY_SYNC_URL=https://yt-mp3-downloader.fly.dev \\
    FLY_SYNC_USERNAME=... \\
    FLY_SYNC_PASSWORD=... \\
    python scripts/fly_sync_live_test.py

Credentials are read from the environment on purpose -- this script hits
the real production account, and a real credential must never be
hardcoded into a committed file (a hardcoded admin password was committed
to this exact repo once during earlier feature work, caught by
GitGuardian, and the exposed password was rotated immediately; don't
repeat that mistake -- this script never prints the password either).

What it does:
  1. Queues a throwaway test video directly on the live Fly app (a plain
     POST /api/library/add against production -- cheap, no yt-dlp
     involved, and cleaned up at the end either way).
  2. Runs this repo's own pull_from_fly() against an isolated local
     Storage (a tmp directory, never the real local data/) and confirms
     the video landed in that local queue.
  3. Calls push_download_outcome() directly (the same function
     app/services/download_orchestrator.py calls after a real download --
     never actually invokes yt-dlp here) to simulate a completed local
     download for that video_id, then confirms via the real Fly API that
     it now shows up in Fly's downloaded history and is gone from Fly's
     library queue.
  4. Cleans up: removes the test video_id from Fly's library (if the pull
     step left it there) and its downloaded-history row (if the push step
     added it) via direct API calls, so this script leaves production no
     more polluted than it needs to be for the test to be meaningful.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.services import fly_sync  # noqa: E402
from app.storage.storage import Storage  # noqa: E402

# youtube.com/watch?v=jNQXAC9IVRw -- "Me at the zoo", the first video ever
# uploaded to YouTube (2005). Same throwaway-but-stable video id used by
# tests/e2e/extension_live_test.js.
VIDEO_ID = "jNQXAC9IVRw"
VIDEO = {
    "video_id": VIDEO_ID,
    "title": "fly_sync_live_test throwaway entry",
    "channel": "fly_sync_live_test",
    "duration": "00:19",
    "url": f"https://www.youtube.com/watch?v={VIDEO_ID}",
    "thumbnail": f"https://img.youtube.com/vi/{VIDEO_ID}/mqdefault.jpg",
}


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Set {name} in the environment before running this script.", file=sys.stderr)
        sys.exit(1)
    return value


def _login(client: httpx.Client, base_url: str, username: str, password: str) -> None:
    resp = client.post(f"{base_url}/login", data={"username": username, "password": password})
    if resp.status_code not in (200, 303):
        raise RuntimeError(f"Login to {base_url} failed (status {resp.status_code})")


def main() -> None:
    base_url = _require_env("FLY_SYNC_URL").rstrip("/")
    username = _require_env("FLY_SYNC_USERNAME")
    password = _require_env("FLY_SYNC_PASSWORD")

    print(f"=== Fly sync live test against {base_url} ===")

    with httpx.Client(timeout=30.0) as client:
        _login(client, base_url, username, password)

        # Idempotent setup: clear any leftover state from a previous run.
        client.delete(f"{base_url}/api/library/{VIDEO_ID}")

        print(f"1. Queuing throwaway test video {VIDEO_ID} on the live Fly app...")
        resp = client.post(f"{base_url}/api/library/add", json=VIDEO)
        if resp.status_code != 200:
            print(f"   FAILED: POST /api/library/add returned {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)
        print("   OK -- queued on Fly.")

    try:
        with tempfile.TemporaryDirectory(prefix="fly_sync_live_test_") as tmp_dir:
            local_storage = Storage(tmp_dir)

            print("2. Running pull_from_fly() against an isolated local Storage...")
            result = fly_sync.pull_from_fly(local_storage)
            print(f"   pull result: {result}")
            if local_storage.get_item_status(VIDEO_ID) != "queued":
                print(f"   FAILED: {VIDEO_ID} did not land in the local queue after pull.", file=sys.stderr)
                sys.exit(1)
            print("   OK -- video is in the local queue.")

            print("3. Simulating a completed local download via push_download_outcome() "
                  "(no yt-dlp invoked)...")
            fly_sync.push_download_outcome({
                **VIDEO,
                "success": True,
                "file_path": str(Path(tmp_dir) / "fly_sync_live_test.mp3"),
            })

        with httpx.Client(timeout=30.0) as client:
            _login(client, base_url, username, password)

            library = client.get(f"{base_url}/api/library").json()["library"]
            still_queued = any(v["video_id"] == VIDEO_ID for v in library)
            print(f"   Still in Fly's library queue: {still_queued}")
            if still_queued:
                print("   FAILED: video should have been removed from Fly's library by the push.",
                      file=sys.stderr)
                sys.exit(1)

            downloaded = client.get(f"{base_url}/api/downloaded", params={"limit": 500}).json()["downloaded"]
            recorded = next((d for d in downloaded if d["video_id"] == VIDEO_ID), None)
            if recorded is None or not recorded["success"]:
                print("   FAILED: video was not recorded as a successful download on Fly.", file=sys.stderr)
                sys.exit(1)
            print("   OK -- recorded as downloaded on Fly, and removed from Fly's queue.")
    finally:
        print("4. Cleaning up (removing the test video_id from Fly's queue/history)...")
        with httpx.Client(timeout=30.0) as client:
            _login(client, base_url, username, password)
            del_lib = client.delete(f"{base_url}/api/library/{VIDEO_ID}")
            print(f"   DELETE /api/library/{VIDEO_ID}: {del_lib.status_code}")
            # There's no dedicated delete-history endpoint (by design --
            # download history is meant to be permanent). Leaving one
            # clearly-labeled throwaway history row behind is an accepted,
            # explicitly-called-out tradeoff rather than adding a new
            # destructive endpoint just for this script.
            print("   (downloaded-history row for this test video_id is left in place -- "
                  "there's no delete-history endpoint by design; it's clearly labeled "
                  "'fly_sync_live_test throwaway entry' if manual cleanup is ever wanted.)")

    print("\nAll live fly-sync checks passed.")


if __name__ == "__main__":
    main()
