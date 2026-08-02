# Full Improvement Plan

A from-scratch pass over the whole app — not just the audit's punch list — covering backend architecture, storage, frontend, real-time updates, deployment, and CI. Each item is checked off as it's implemented; unchecked items are documented scope, not yet done.

This builds on [01-audit.md](01-audit.md) / [02-fixes.md](02-fixes.md), which are already fully applied.

## Backend / API

- [x] **Real WebSocket progress broadcasting.** The previous `/ws` stub was removed as dead code in [02-fixes.md](02-fixes.md). Re-added properly this time: `downloader.py`'s progress hook now reports through a callback, `api/routes.py`'s background download task broadcasts `{type: "progress", video_id, percent}` / `{type: "download_complete", ...}` over the connection manager, and `app.js` updates the UI live instead of only polling.
- [x] **Config validation.** `config.json` was a raw dict with no validation — `audio_quality` could be set to any string via `POST /api/config` with no error (verified: previously returned 200 for `audio_quality: "999"`). `POST /api/config` now takes a Pydantic `ConfigUpdate` model (`api/routes.py`) validating `audio_quality` against the allowed bitrates and `format` against supported formats; invalid values now get a 422.
- [x] **Atomic, lock-safe JSON writes.** `Storage._write_json` did a plain `open(...).write()` with no locking. Since downloads run as a background task while the API can still be hit concurrently (e.g. removing a queue item mid-download), two writers could interleave and corrupt `library.json`/`downloaded.json`. Fixed with write-to-temp-file-then-atomic-rename plus a per-file lock.
- [x] **Background task error handling.** `download_task` in `api/routes.py` had no try/except around each download — an unexpected exception (e.g. disk full) would kill the background task silently for the rest of the batch. Wrapped per-item with error capture and logging; failures are now recorded distinctly rather than just vanishing from the queue.
- [x] **Structured logging.** The API path used `rich.console.Console.print` (meant for CLI output) for error reporting, which doesn't integrate with any log aggregation and prints straight to stdout with no levels. Added Python's standard `logging` module for the FastAPI/background-task path; kept `rich` for the CLI scripts in `scripts/` where it's genuinely a terminal UI.
- [x] **API input validation.** `/api/search`'s `limit` field had no upper bound (a client could request `limit=100000`). Added a bounded range via Pydantic `Field(ge=1, le=50)`.
- [x] **Replace flat JSON storage with SQLite.** `library.json`/`downloaded.json` are gone (removed from disk, still recoverable via git history); `db.py` now backs the library queue and download history with SQLite (WAL mode), giving indexed `video_id` lookups instead of a full-list scan for every `is_downloaded`/`is_in_library`/status check. `scripts/migrate_to_sqlite.py` did the one-time import -- ran it for real against this repo's data and verified the count matches exactly: 655 downloaded entries in, 655 in `downloads.db`. `config.json` stays JSON as planned (no query needs, single small object). `utils.py`'s `Storage` public API is unchanged, so `api/routes.py` needed no changes beyond `get_status` switching to the new `count_library()`/`count_downloaded()` (`SELECT COUNT(*)` instead of loading the full list just to call `len()`).
- [ ] **Auth / access control.** Still intentionally out of scope for a LAN-only personal tool per [01-audit.md](01-audit.md); revisit only if ever exposed beyond the home network.

## Frontend

- [ ] **Split `app.js` into modules.** It's a single 800+ line file with everything as global functions/state (`api.js`, `search.js`, `queue.js`, `ui.js` would be the natural split). Not done in this pass — it's a large, UI-testing-heavy refactor better done as its own reviewed change rather than blind autonomous edits to a file with no test coverage.
- [x] **Live progress in the UI.** Wired up to the new WebSocket broadcast above — queue items now show real download percentage instead of only a static "downloading" dot.
- [x] **Fixed light-theme navbar bug.** `landing.js`'s scroll handler set an inline `navbar.style.background = 'rgba(10, 10, 15, ...)'` on scroll, which overrode `landing.css`'s `[data-theme="light"] .navbar` rule (inline styles beat any stylesheet selector) — so scrolling in light mode turned the navbar dark. Replaced with a `.scrolled` class toggle so the theme's own CSS controls the color; also dropped the now-unused `lastScroll` variable.
- [x] **Removed dead progress-bar functions.** `app.js`'s `showDownloadProgress`/`hideDownloadProgress`/`updateProgress` referenced `#download-progress`/`#progress-fill`/`#progress-text` elements that don't exist anywhere in `app.html` and were never called — leftover from before the WebSocket-based per-item progress text landed above.

## Tooling / Deployment

- [x] **CI workflow.** Added `.github/workflows/ci.yml` running the same checks as `make check` (syntax, mypy, ruff, flake8, pytest) directly on every push/PR to `master` — invoked as plain commands rather than via `make`, since the CI runner installs dependencies straight into the system Python rather than creating a `venv/`, which is what the Makefile's paths assume.
- [x] **Dockerfile.** Added a `Dockerfile` (+ `.dockerignore`) so the app can run reproducibly without manually managing a venv/FFmpeg install — useful given the README's own "Auto-Start on Boot" section already treats this as a long-running home-server service.
- [x] **docker-compose.yml.** Added with `downloads/`, `config.json`, and `downloads.db` mounted from the host so the library/settings persist across container rebuilds -- the obvious default for this app's data files, documented in the README's new Docker section.

## Note on git-tracking downloads.db

`downloaded.json` was previously tracked in git (the old `.gitignore` comment said as much: "keep tracked songs in downloaded.json instead"), which gave a free, human-readable backup of download history in the repo's commit log. `downloads.db` is now tracked the same way for parity -- but SQLite is a binary format, so every future download will produce an opaque, undiffable commit instead of a readable JSON diff, and the repo will grow by a full ~300KB+ (and growing) binary blob's worth per commit rather than a small text diff. If that tradeoff isn't wanted, add `downloads.db` to `.gitignore` and rely on the Docker volume / regular filesystem backups instead.

## Explicitly not planned

- A frontend framework (React/Vue) or build step — the app's small enough that vanilla JS is the right call; a framework would be pure overhead.
- Multi-user support — this is a single-user LAN tool by design.
