# File/Directory Reorganization — 2026-08-02

Restructured from a flat set of top-level modules into a proper `app/` package, with runtime data separated into `data/`.

## Before

```
youtube-downloader/
├── app.py
├── api/{__init__.py, routes.py}
├── downloader.py
├── search.py
├── utils.py            (pure helpers + Storage class, mixed concerns)
├── db.py
├── ws_manager.py
├── config.json
├── downloads.db
├── static/, templates/, scripts/, tests/, docs/
```

## After

```
youtube-downloader/
├── app/
│   ├── __init__.py
│   ├── main.py          (was app.py)
│   ├── ws_manager.py
│   ├── utils.py          (pure helpers only: sanitize_filename, format_duration, extract_video_id)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── downloader.py
│   │   └── search.py
│   └── storage/
│       ├── __init__.py
│       ├── db.py
│       └── storage.py    (Storage facade, moved out of utils.py)
├── data/
│   ├── config.json
│   └── downloads.db
├── static/, templates/, scripts/, tests/, docs/
```

## Rationale

- **`app/` as a real package**: groups everything by role (`api` = HTTP layer, `services` = business logic/yt-dlp, `storage` = persistence) instead of a flat pile of same-level modules. Matches common FastAPI project conventions.
- **`Storage` split out of `utils.py`**: `utils.py` previously mixed a stateful persistence class with three unrelated pure functions (`sanitize_filename`, `format_duration`, `extract_video_id`). The pure functions now live in `app/utils.py`; `Storage` moved to `app/storage/storage.py` next to the `db.py` it wraps.
- **`data/` for runtime state**: `config.json` and `downloads.db` are data the app reads/writes at runtime, not source code -- separating them from `app/` makes it obvious at a glance what's code (reviewed, tested, git-diffable in the normal sense) versus what's this particular install's state. `Storage.__init__` now defaults `base_dir="data"` and creates the directory if missing.
- **`downloads/` (the actual MP3s) stays at repo root, untouched.** Moving actual media files risked breaking any existing paths already recorded in `data/downloads.db`'s `file_path` column, or orphaning files if anything external already points at the old location. Only the app's own small metadata files moved.

## What changed to make this work

- Every internal import switched to absolute `app.*` paths (e.g. `from app.services.downloader import YouTubeDownloader`), since `app/main.py` can no longer rely on being run from its own directory.
- **Run command changed**: `python app.py` → `python -m app.main` (updated in `run.sh`, the systemd example in the README, and `Dockerfile`'s `CMD`). Running `python app/main.py` directly does *not* work -- Python would add `app/` itself to `sys.path` rather than the repo root, breaking the `from app.api.routes import ...` absolute imports.
- `Dockerfile`'s `WORKDIR` renamed from `/app` to `/srv` to avoid confusion with the `app` Python package now living inside it.
- `docker-compose.yml` volumes updated: `./data:/srv/data` instead of separately mounting `config.json`/`downloads.db`.
- `data/` added to `.dockerignore` -- runtime data shouldn't be baked into the built image (the compose volume mount supplies it).
- Makefile/CI simplified to target `app/` as a directory (`mypy app/`, `flake8 app/`, `find app -name "*.py" ...`) instead of listing every file individually, since that list only kept growing as files were added.
- Fixed a latent, unrelated bug surfaced while testing `python -m app.main` as a real subprocess: the startup banner's emoji `print()` calls raised `UnicodeEncodeError` when stdout isn't UTF-8 (e.g. backgrounded/redirected on Windows, which falls back to cp1252). Added a `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` guard before those prints.

## Verification performed

- Full check suite (syntax, mypy, ruff, flake8, pytest -- 20 tests) passes against the new layout.
- Live `TestClient` smoke test: `/`, `/app/name`, `/health`, `/api/status` all respond correctly, and `/api/status` still reports the real 655 downloaded entries from `data/downloads.db` (confirming the data survived the move).
- Booted the app for real via `python -m app.main` as a background subprocess (matching exactly what `run.sh` invokes) and confirmed `/health` responds and the startup banner prints without crashing.
