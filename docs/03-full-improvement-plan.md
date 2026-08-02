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
- [ ] **Replace flat JSON storage with SQLite.** 655+ growing history entries in a single JSON file means every read/write is O(n) full-file rewrite. Not done in this pass — it's a bigger migration (schema, migration script for existing `downloaded.json`) that deserves its own review rather than being bundled here.
- [ ] **Auth / access control.** Still intentionally out of scope for a LAN-only personal tool per [01-audit.md](01-audit.md); revisit only if ever exposed beyond the home network.

## Frontend

- [ ] **Split `app.js` into modules.** It's a single 800+ line file with everything as global functions/state (`api.js`, `search.js`, `queue.js`, `ui.js` would be the natural split). Not done in this pass — it's a large, UI-testing-heavy refactor better done as its own reviewed change rather than blind autonomous edits to a file with no test coverage.
- [x] **Live progress in the UI.** Wired up to the new WebSocket broadcast above — queue items now show real download percentage instead of only a static "downloading" dot.

## Tooling / Deployment

- [x] **CI workflow.** Added `.github/workflows/ci.yml` running the same checks as `make check` (syntax, mypy, ruff, flake8, pytest) directly on every push/PR to `master` — invoked as plain commands rather than via `make`, since the CI runner installs dependencies straight into the system Python rather than creating a `venv/`, which is what the Makefile's paths assume.
- [x] **Dockerfile.** Added a `Dockerfile` (+ `.dockerignore`) so the app can run reproducibly without manually managing a venv/FFmpeg install — useful given the README's own "Auto-Start on Boot" section already treats this as a long-running home-server service.
- [ ] **docker-compose with a persistent volume for `downloads/`.** Sketched but not added — depends on where the user actually wants the downloads volume mounted on their machine, which isn't something to guess at.

## Explicitly not planned

- A frontend framework (React/Vue) or build step — the app's small enough that vanilla JS is the right call; a framework would be pure overhead.
- Multi-user support — this is a single-user LAN tool by design.
