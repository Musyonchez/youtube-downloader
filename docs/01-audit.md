# Project Audit — 2026-08-02

Scope: full repo read-through (`app.py`, `api/routes.py`, `downloader.py`, `search.py`, `utils.py`, templates, static assets, config, tooling). No runtime testing performed.

## Overview

FastAPI web app that searches YouTube (via `yt-dlp`), queues videos in `library.json`, downloads them as tagged MP3s, and records history in `downloaded.json`. No database — flat JSON files. Vanilla JS/CSS frontend, no build step.

## Findings

### Correctness / consistency

- **README song count is inconsistent.** The features section says "655 songs" (matches `downloaded.json`, verified: 655 entries), but the "Tech Stack → Storage" section still says *"Track 6,000+ songs efficiently"* ([README.md:384](../README.md#L384)). Leftover from before the count was corrected elsewhere.
- **Unused dependencies.** `pillow` and `requests` are listed in [requirements.txt](../requirements.txt) but never imported anywhere in the codebase.
- **WebSocket endpoint is a stub.** `/ws` in [app.py:59-69](../app.py#L59-L69) just echoes messages back; `ConnectionManager.broadcast` is never called from the download flow. Real-time progress described in the README isn't wired up — the frontend must be polling instead (worth confirming in `app.js`).
- **Template rendering is hand-rolled string replacement**, not Jinja2 despite Jinja-like syntax in the HTML ([app.py:90-142](../app.py#L90-L142)). Each mode does ~9 `content.replace(...)` calls matching on literal UI text. This is fragile: if any of those UI strings change in `templates/app.html`, the mode-specific text silently breaks with no error, and any string that happens to reappear elsewhere in the page gets blanked too.

### Security

- **CORS config is contradictory/unsafe as written**: `allow_origins=["*"]` with `allow_credentials=True` ([app.py:19-25](../app.py#L19-L25)). Most browsers reject wildcard origins when credentials are allowed, so this either silently fails for credentialed requests or (if something changes it to reflect origins) opens the API to any site. Fine for trusted local-network use as-is, but flag before this is ever exposed beyond a LAN.
- **No auth on any API route.** Acceptable for a local/LAN personal tool (per README's design intent), but worth stating explicitly if this is ever deployed somewhere reachable beyond the home network.

### Dead / legacy code

- [templates/old.html](../templates/old.html) and [static/css/style.css](../static/css/style.css) are explicitly marked "legacy" and still served via `/old` ([app.py:81-87](../app.py#L81-L87)). Candidate for removal if the old UI is no longer needed.
- [download_temp.py](../download_temp.py) and [rename_bible.py](../rename_bible.py) are one-off personal scripts (hardcoded playlist URL, hardcoded Bible book renaming) committed at repo root alongside the app's core modules. They work standalone but aren't part of the app — consider moving to a `scripts/` subfolder to separate them from `app.py`/`downloader.py`/`search.py`/`utils.py`.

### Tooling

- `make check` / `make lint` swallow failures with `|| true` ([Makefile:47](../Makefile#L47), [Makefile:52-53](../Makefile#L52-L53)) — mypy, ruff, and flake8 issues are printed but never fail the command. There's no CI enforcing them either, so lint/type errors can accumulate silently.
- Makefile and `run.sh` hardcode `venv/bin/...` (POSIX layout). On this Windows machine that requires Git Bash/WSL — running `make` from PowerShell/cmd directly won't find `venv/bin/python`.
- No automated tests (no `pytest`, no `tests/` dir). `search.py` and `downloader.py` each have a manual `test_*()` function gated behind `if __name__ == "__main__"`, which only runs against live YouTube — not a real test suite.

## Not evaluated

- Frontend JS behavior (`app.js`, `landing.js`) — read as static files, not exercised in a browser.
- Actual download/tagging behavior against live YouTube.
