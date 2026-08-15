"""Run the app for E2E tests with YouTubeSearcher mocked.

Not used in production. Exists so CI can smoke-test the real browser-facing
behavior (see docs/05-browser-verification.md) without hitting live YouTube
on every push -- that would be flaky and rate-limit-prone. This is exactly
the kind of gap that let a real search-breaking regression through
untested: unit/HTTP-level tests never exercise what the browser-rendered
JS actually sends and renders.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402
from app.services import search as search_module  # noqa: E402

FAKE_RESULTS = [
    {
        "video_id": "dQw4w9WgXcQ",
        "title": "Fake Test Video One",
        "channel": "Test Channel",
        "duration": "03:30",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
    },
    {
        "video_id": "9bZkp7q19f0",
        "title": "Fake Test Video Two",
        "channel": "Test Channel",
        "duration": "04:12",
        "url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
        "thumbnail": "https://img.youtube.com/vi/9bZkp7q19f0/mqdefault.jpg",
    },
]


def fake_search_by_name(self, query, limit=10):
    return FAKE_RESULTS[:limit]


if __name__ == "__main__":
    with patch.object(search_module.YouTubeSearcher, "search_by_name", fake_search_by_name):
        uvicorn.run(app, host="127.0.0.1", port=8000)
