# 09 — Comprehensive Multi-Agent Audit Findings

Produced by the playbook in [08-comprehensive-audit-prompt.md](08-comprehensive-audit-prompt.md):
6 parallel specialized agents (Architecture, Bugs, UI/UX, Backend/Data, Security/Perf,
Testing/DX) audited the repo independently, findings below are cross-checked and merged.

## Executive summary

**Health:** solid for a personal single-user tool. No P0s. The one real theme that
cuts across three agents (Bugs, Backend/Data, Testing) is **download failure handling**:
a failed download vanishes with no record, no retry path, and (in one code path) can
even delete an already-succeeded file. That's the headline risk. Everything else is
incremental hardening or polish.

**Top 10 priorities:**
1. Lock against concurrent/duplicate `/api/download` runs (data corruption risk) — AUD-01
2. Record failed downloads instead of discarding them silently — AUD-02
3. Fix `is_downloaded()` to check `success`, or AUD-02's fix breaks retry forever — AUD-03
4. Make the download error-reporting path itself exception-safe (can skip cleanup or delete a finished file) — AUD-04
5. Batch the N+1 status-lookup queries (search/playlist/add-multiple) — AUD-05
6. Distinguish "Downloaded" vs "Queued" result badges (currently identical) — AUD-06
7. Validate `download_dir` against a base path (arbitrary-directory writes) — AUD-07
8. Add accessible labels to settings form, search input, modal, toasts — AUD-08 to AUD-11
9. Wire up or remove the dead `add-multiple` bulk-download endpoint + `selectedVideos` — AUD-12
10. Add the highest-value missing tests: `download_task`, route-level `TestClient` coverage — AUD-19

**Launch readiness:** N/A in the traditional sense (personal LAN tool, no external users),
but "safe to keep growing the library on" — yes, all 29 tracked findings are fixed.

## What's already good — don't touch

- `app/storage/db.py`'s hand-rolled SQLite schema (no ORM) — right-sized for 2 tables.
- `Storage` facade splitting JSON config vs. SQLite data, with rationale documented.
- Config writes are atomic (temp file + `os.replace`) — a pattern the download-state
  code doesn't share yet (see AUD-02/AUD-14) but should.
- FFmpeg-missing fail-fast + orphan cleanup (docs/07) — correctly fixes its trigger.
- CORS (`allow_origins=["*"]` + `allow_credentials=False`) — the only safe combination.
- Error responses are pre-scrubbed — no stack traces/paths ever reach the client.
- Dependency versions are current, no known CVEs.
- Loading/empty/skeleton states, localStorage-persisted preferences, alt text + lazy
  thumbnails, `aria-label`s on most icon buttons, confirm() on destructive queue actions.
- Shared navbar partial, WAL-mode SQLite, `broadcast_threadsafe`'s dead-loop guard.

---

## Master issue table

| ID | Sev | Area | Finding | Evidence | Fix | Status |
|----|-----|------|---------|----------|-----|--------|
| AUD-01 | P1 | Backend/Bugs | No lock across concurrent `/api/download` calls — same video can be downloaded twice in parallel, corrupting the output file | `app/api/routes.py:290-308`; reproduced live by both Bugs and Backend agents | Server-side in-flight lock/set on `video_id`; frontend also guards `downloadSingle()` | **Fixed** |
| AUD-02 | P1 | Backend | Failed downloads are never recorded — item is removed from queue, nothing written to `downloaded`, no retry path | `app/api/routes.py:270-287` (else branch never calls `add_to_downloaded`) | Insert a `success=False` row on failure | **Fixed** |
| AUD-03 | P1 | Backend | `is_downloaded()` doesn't filter on `success` — fixing AUD-02 naively makes every failed video permanently un-retryable | `app/storage/db.py:114-117` | Add `AND success = 1` to the query | **Fixed** |
| AUD-04 | P1 | Bugs | Download error-reporting itself isn't exception-safe (console emoji on cp1252 encoding) — can skip orphan cleanup or, worse, delete an already-finished file | `app/services/downloader.py:142-147`, reproduced live | Wrap `console.print` in try/except in the handler; log first | **Fixed** |
| AUD-05 | P2 | Backend/Perf | N+1 status-lookup pattern: up to 2 locked SQLite round-trips per item, ×100 (search) or ×1000 (playlist) | `app/storage/storage.py:117-124` called in a loop, `app/api/routes.py:70-77,119-137,182-186` | Batch `SELECT ... IN (...)` for downloaded/library ids, compute status in Python | **Fixed** |
| AUD-06 | P1 | UI/UX | "Downloaded" and "Queued" result badges are visually identical (same color) | `static/js/search.js:260-265`, `static/css/app.css:437-447` | Distinct badge colors per status | **Fixed** |
| AUD-07 | P2 | Security | `download_dir` accepted with zero validation — any LAN client can redirect downloads to an arbitrary writable path | `app/api/routes.py:47-51`, `app/services/downloader.py:36-42` | Validate against an allowed base dir | **Fixed** |
| AUD-08 | P2 | A11y | Settings modal labels have no `for` attribute | `templates/app.html:28-40` | Add `for="audio-quality"` / `for="download-dir"` | **Fixed** |
| AUD-09 | P2 | A11y | Search input has no accessible label | `templates/app.html:68-73` | `aria-label` | **Fixed** |
| AUD-10 | P2 | A11y | Settings modal has no `role="dialog"`, no focus trap, no focus-on-open | `templates/app.html:15-47`, `static/js/ui.js:102-117` | Add ARIA + focus management | **Fixed** |
| AUD-11 | P2 | A11y | Toasts aren't announced to screen readers | `templates/app.html:178` | `role="status" aria-live="polite"` | **Fixed** |
| AUD-12 | P3 | Product/Dead code | `/api/library/add-multiple` + `selectedVideos` state exist but nothing calls them — abandoned bulk-add feature | `app/api/routes.py:175-195`, `static/js/state.js:5` | Remove (no bulk-select UI planned) | **Fixed (removed)** |
| AUD-13 | P2 | UI/UX | Queued (non-"new") result cards look fully clickable/hoverable but have no click target | `static/js/search.js:213-298`, `static/css/app.css:386-393` | Dim + `cursor:not-allowed` to match downloaded cards | **Fixed** |
| AUD-14 | P2 | Backend | Non-atomic remove-then-record in `download_task` can lose a completed download across a crash between the two writes | `app/api/routes.py:270-287` | Record outcome before removing from queue | **Fixed** |
| AUD-15 | P2 | UI/UX | Two badges (`.status-badge`, `.queue-badge`) fail WCAG AA contrast (white text on light green/red) | `static/css/app.css:437-447,739-751` | Darken backgrounds | **Fixed** |
| AUD-16 | P3 | UI/UX | Results filter row can overflow on ≤360px phones (no `flex-wrap`) | `static/css/app.css:150-196,1066-1125` | `flex-wrap: wrap` on `.filter-toggle` | **Fixed** |
| AUD-17 | P2 | Bugs | `downloadSingle()` shows "Download complete!" even when the download failed (only checks queue membership) | `static/js/queue.js:104-123` | Trust the WS `download_complete.success` flag | **Fixed** |
| AUD-18 | P3 | Architecture | `download_task` (real orchestration logic) lives in the API layer, not services | `app/api/routes.py:235-287` | Moved to `app/services/download_orchestrator.py`; routes.py now a thin wrapper | **Fixed** |
| AUD-19 | P1 | Testing | Zero test coverage for `download_task`, the core queue/download state machine | `app/api/routes.py:235-287` | `tests/test_download_orchestrator.py` (core logic) + `tests/test_download_task.py` (routes wrapper/lock) | **Fixed** |
| AUD-20 | P2 | Testing | No `TestClient`-based route tests at all | `tests/` | New `tests/test_api_routes.py` + `tests/test_history_page.py` | **Fixed** |
| AUD-21 | P3 | Security | `sanitize_filename` doesn't handle Windows reserved device names, length caps, or control chars | `app/utils.py:25-31` | Reserved-name/empty/length/control-char handling added | **Fixed** |
| AUD-22 | P2 | Backend | Filename collision (same channel+title, different `video_id`) silently reuses the first file, second video never downloaded | `app/services/downloader.py:88-96` | Filename now includes `[video_id]`; cleanup switched from `glob()` to literal-prefix matching (glob treats `[...]` as a char class) | **Fixed** |
| AUD-23 | P3 | Perf | Unthrottled WebSocket progress broadcasts (fires on nearly every yt-dlp chunk) | `app/services/downloader.py:50-68` | Throttled to ≥1% delta or ~250ms, reset per video; final 100% always sent | **Fixed** |
| AUD-24 | P3 | Security | Loose URL validation (`'youtube.com' in url`) allows SSRF-flavored probing via yt-dlp's generic extractor | `app/services/search.py:141-149` | Host allowlist via `urlsplit`, checked against actual netloc | **Fixed** |
| AUD-25 | P4 | Architecture | Dead code: `download_batch`, `test_download`/`test_search()` `__main__` blocks, duplicate of `download_task`'s loop | `app/services/downloader.py:183-233`, `app/services/search.py:152-173` | Removed; also added `logger.exception` calls to `search.py`'s except blocks | **Fixed** |
| AUD-26 | P3 | Product | `GET /api/downloaded` (download history) has a working backend, zero UI | `app/api/routes.py:212-216` | New `/history` page: filter (All/Downloaded/Failed), search, pagination, Retry on failed items | **Fixed** |
| AUD-27 | P3 | UI/UX | FAQ accordion buttons don't expose `aria-expanded` | `templates/index.html:232-297`, `static/js/landing.js:5-18` | `aria-expanded`/`aria-controls`/`id` wired up | **Fixed** |
| AUD-28 | P4 | Perf | `renderQueue()` fully rebuilds the DOM every 1s poll regardless of change | `static/js/queue.js:2-34` | Skips the rebuild when the queue's video-id set + downloading state are unchanged | **Fixed** |
| AUD-29 | P4 | A11y | `youtube-preview-btn` relies on `title` only, not `aria-label` | `static/js/search.js:247-256` | Add `aria-label` | **Fixed** |

Full per-area detail (all findings, including P3/P4 not tracked above) is preserved
in the audit agents' original reports if needed later — this table keeps the ones
worth tracking.

## Roadmap

**All 29 tracked findings are fixed** (commits f9975e2, e743ea1, and the
follow-up pass that closed AUD-18/20-24/26-28). Nothing outstanding from
this audit round. Two notable behavior changes worth knowing about:

- Downloaded filenames now include `[video_id]` (e.g.
  `Artist - Title [dQw4w9WgXcQ].mp3`) to prevent same-titled videos from
  colliding on one file (AUD-22). Existing files aren't renamed —
  only new downloads use the new pattern.
- A new `/history` page exists (AUD-26), linked from the navbar, backed by
  the `/api/downloaded` endpoint that already existed.

Re-run the [08-comprehensive-audit-prompt.md](08-comprehensive-audit-prompt.md)
playbook for a future full-repo pass once the project has grown enough to
justify it again.
