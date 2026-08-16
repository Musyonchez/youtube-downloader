# Post-Auth Audit Findings

## How this doc came to exist

This doc was supposed to already exist, with findings 16-1 through 16-26,
before implementation started on the first pass -- that's the normal order
(see docs/08/09's "audit first, modify later" ground rule, and how docs/11
-> docs/12/13 worked). It didn't, as of the first implementation pass: no
commit on `master`, any branch, or any worktree had it. That gap turned out
to be a workflow slip, not a missing doc -- it had been written and staged
in the main repo's working directory, but not committed before this
isolated worktree branched off, so the worktree's git history genuinely
never contained it. First pass therefore reconstructed and implemented only
the 16 finding IDs specified in enough concrete detail to act on
responsibly, and explicitly declined to invent the other 10 rather than
fabricate plausible-sounding findings under real-looking IDs. Those 10 were
then supplied verbatim (from the actual doc that had been written) and
implemented in a second pass. All 26 IDs are covered below.

## Findings

Each finding below is marked **Implemented** with what changed.

### P1 / Immediate

- **16-1 — Registration race lets two different accounts get created.**
  **Implemented.** `register_submit` used to do `count_users() == 0` then
  `create_user()` as two separate storage calls; two concurrent requests
  for two *different* usernames could each see zero users before either
  committed (the old `IntegrityError` backstop only caught a same-username
  collision, not this). Fixed with `Database.create_user_if_first()` /
  `Storage.create_user_if_first()`: the count check and the insert now
  happen under one `_lock` acquisition. See `app/storage/db.py`,
  `app/storage/storage.py`, `app/main.py`. Tests:
  `tests/test_db.py::test_create_user_if_first_refuses_second_account`,
  `tests/test_auth_routes.py::test_register_concurrent_different_usernames_only_one_wins`
  (actually races two threads against it).

- **16-2 — No login rate limiting.** **Implemented.** In-process, per-username
  cooldown that doubles on each consecutive failure (1s, 2s, 4s, ... capped
  at 30s), reset on success. See `app/main.py`'s `_login_cooldown_remaining`
  / `_record_login_failure` / `_clear_login_failures`. Deliberately not a
  new dependency (e.g. slowapi) given the single-account scope. Tests:
  `tests/test_auth_routes.py::test_login_rate_limit_blocks_rapid_repeated_failures`,
  `::test_login_rate_limit_is_per_username`.

- **16-3 — Mobile navbar broken on /login and /register.** **Implemented.**
  Those two pages load `nav.css` but never `app.css`/`landing.css`, which
  is where the `.nav-links`/`.mobile-menu-btn` responsive breakpoint used
  to live -- so the navbar never collapsed for them on narrow screens. The
  shared breakpoint now lives in `nav.css` itself (at 968px, the wider of
  the two page-specific values), so every page that includes the navbar
  gets it for free; `app.css`/`landing.css` keep only their own
  page-specific rules at that same breakpoint.

- **16-4 — README's auth sections reference the removed Basic Auth.**
  **Implemented.** `README.md`'s project-structure listing still named
  `app/auth.py` (removed when docs/15 replaced Basic Auth with session
  auth) and the deployment section still described `APP_USERNAME`/
  `APP_PASSWORD`. Rewrote both to describe `/register`, `/login`,
  `SECRET_KEY`, and the `FLY_APP_NAME`/`ENVIRONMENT` Secure-cookie signal.

### P2 / Soon

- **16-5 — `.auth-error` text contrast fails WCAG AA in light theme.**
  **Implemented.** `color: var(--warning)` on the error banner's tinted
  background clears 4.5:1 against the dark theme's card background
  (~4.86:1) but drops to ~2.8:1 against the light theme's near-white card
  background. Kept `--warning` for dark (already passing) and added a
  `[data-theme="light"] .auth-error { color: var(--warning-strong); }`
  override (~5.3:1) for light -- reusing the token already defined for
  white-text badges rather than inventing a new color. See
  `static/css/auth.css`.

- **16-6 — Duplicate `Storage` instances.** **Implemented.** `app/main.py`
  used to construct its own `Storage()` for the auth routes, separate from
  `app/api/routes.py`'s module-level `storage` -- both pointed at the same
  `data/` directory, so production ran two live sqlite3 connections against
  one file for no benefit. `app/main.py` now imports and reuses
  `app.api.routes.storage` as `auth_storage` instead of constructing a
  second instance. Tests still isolate each module's reference
  independently (existing pattern, unaffected).

- **16-7 — `https_only` tied to whether `SECRET_KEY` happens to be set.**
  **Implemented.** `SECRET_KEY` can legitimately be set in local dev too
  (e.g. to test session persistence across restarts), which would have
  wrongly forced `Secure` cookies over plain HTTP and silently broken
  login. Replaced with `IS_PRODUCTION = bool(FLY_APP_NAME or ENVIRONMENT
  == "production")` -- `FLY_APP_NAME` is set automatically by the Fly.io
  runtime for every deployed app. See `app/main.py`.

- **16-8 — Unbounded download-history query.** **Implemented.** The
  `downloaded` table only ever grows (every attempt, success or failure,
  kept permanently); `get_downloaded()`/`/api/downloaded` used to return
  the *entire* table on every call. Added `limit`/`offset`/`descending`
  params through `Database.get_downloaded` -> `Storage.load_downloaded` ->
  `GET /api/downloaded` (now also returns `total`); the `/history` page
  fetches bounded batches (200 at a time, newest-first) and offers a "Load
  more" control instead of pulling everything on every page load. See
  `app/storage/db.py`, `app/storage/storage.py`, `app/api/routes.py`,
  `static/js/history.js`.

- **16-9 — No server-side password minimum length.** **Implemented.** Added
  an 8-character minimum in `register_submit`, same "server is the real
  boundary" pattern already used for the registration-closed check. See
  `app/main.py`.

### P3 / Later

- **16-11 — docs/08's stale "Project context."** **Implemented.** It
  claimed "no login system... not a gap to re-flag" and listed
  authentication as out of scope; both were true when written for a
  LAN-only deployment and became false once docs/15 shipped real
  session-cookie auth on a public Fly.io deploy. Corrected in place, with
  a note explaining why it changed rather than silently rewriting history.
  See `docs/08-comprehensive-audit-prompt.md`.

- **16-13 — Missing tests: open-redirect, empty-credential registration,
  already-authenticated login/register redirect.** **Implemented.** Added
  to `tests/test_auth_routes.py`:
  `test_login_open_redirect_next_falls_back_to_default` /
  `test_login_open_redirect_allows_safe_relative_next`,
  `test_register_rejects_empty_username_or_password`,
  `test_register_get_redirects_when_already_authenticated` /
  `test_login_get_redirects_when_already_authenticated`. (The existing
  `_safe_next_path` open-redirect guard and the already-authenticated
  redirects in `login_form`/`register_form` were already implemented in
  docs/15 -- this finding was specifically about the missing test
  coverage, not missing behavior.)

- **16-17 — Hamburger button never reflects open/closed state
  (`aria-expanded`).** **Implemented.** `.mobile-menu-btn` was hardcoded
  `aria-expanded="false"` in the markup and never updated. Added
  `aria-controls="mobileMenu"` and have `toggleMobileMenu()` (and the
  outside-click auto-close handler) update `aria-expanded` to match actual
  state. See `templates/partials/navbar.html`, `static/js/nav.js`.

- **16-18 — `--accent` as text color falls just under WCAG AA on dark
  theme.** **Implemented.** `.nav-links a.active` and `.stat strong` use
  `--accent` as a page-background text color, at ~4.32:1 on dark theme
  (documented as a known, deliberate tradeoff in `variables.css` -- the
  button-background role was prioritized there since it's higher-traffic).
  Rather than reopening that tradeoff, added `--accent-strong` (a lighter
  copper, ~6.5:1 on dark; equal to `--accent` in light theme, where plain
  `--accent` already passes) reserved for exactly this text-on-page-
  background role, and pointed both selectors at it. See
  `static/css/variables.css`, `static/css/nav.css`, `static/css/app.css`.

- **16-19 — Duplicate `showToast` in `ui.js` and `history.js`.**
  **Implemented.** Both defined an identical function. Moved the one
  definition into `static/js/cards.js`, already shared by both the app
  page and the history page, and removed both duplicates.

- **16-20 — Stale "unauthenticated LAN client" comment in
  `app/utils.py`.** **Implemented.** The comment on
  `_WINDOWS_SENSITIVE_DIRS`/`_POSIX_SENSITIVE_DIRS` described the abuse
  case as "an unauthenticated LAN client" -- no longer accurate now that
  every route requires a logged-in session (docs/15). Updated to describe
  the current threat model (the logged-in account itself) while noting the
  historical LAN-only context.

- **16-10 — `/api/library/add` accepts an arbitrary `url` with no host
  validation.** **Implemented.** Unlike `/api/video-info`/
  `/api/playlist-info`, which run their `url` through
  `searcher.validate_url`'s SSRF-safe host allowlist, `/api/library/add`
  handed `video.url` straight to storage (and from there, eventually, to
  yt-dlp at download time) with no check -- reachable directly, not just
  via the normal search -> add-to-library UI path. Added the same
  `validate_url` check before accepting the video. Low real-world severity
  now that the app is authenticated, but inconsistent with the hardening
  already done on the sibling routes. See `app/api/routes.py`. Test:
  `tests/test_api_routes.py::test_add_to_library_rejects_url_with_disallowed_host`.

- **16-12 — Unguarded two-write sequence per download outcome.**
  **Implemented.** `add_to_downloaded()` then `remove_from_library()` are
  two separate SQLite writes with no transaction spanning them; if the
  second raised after the first committed, the exception used to propagate
  straight out of the batch loop, aborting every video still queued behind
  it. Wrapped `remove_from_library()` in a try/except that logs and moves
  on to the next video instead -- the single video can still end up
  duplicated (recorded as downloaded *and* still queued; this isn't a real
  transaction), but that's now an isolated, logged anomaly instead of a
  silent whole-batch abort. See `app/services/download_orchestrator.py`.
  Test:
  `tests/test_download_orchestrator.py::test_remove_from_library_failure_does_not_abort_the_batch`.

- **16-14 — Frontend never detects auth loss mid-session.**
  **Implemented.** `loadStatus()`/`loadQueue()` only `console.error`'d a
  401, so an expired/logged-out-elsewhere session left the UI polling
  forever with a frozen state and no visible explanation; the WS reconnect
  loop didn't special-case the `4401` auth-close code either, so a
  logged-out tab kept retrying a handshake that could only ever be
  rejected again. `apiCall()` (api.js) now redirects to
  `/login?next=<path>` on any 401, covering every call site including the
  poll loops in queue.js; the WS `onclose` handler redirects the same way
  on code `4401` instead of scheduling a reconnect. See `static/js/api.js`,
  `static/js/websocket.js`.

- **16-15 — Unpinned dependencies, no lockfile.** **Implemented.** Added
  `requirements.lock` (full resolved dependency closure, exact versions,
  generated from a clean venv against `requirements.txt` -- see its header
  for the regenerate command). Dockerfile, CI, and `make install` now
  install from it instead of `requirements.txt`'s open `>=` bounds;
  `requirements.txt` stays as the human-edited loose source of truth. See
  `requirements.lock`, `Dockerfile`, `.github/workflows/ci.yml`,
  `Makefile`.

### P4 / Future

- **16-16 — `registration_open()` re-queries SQLite on every render,
  forever.** **Implemented.** It's a Jinja global called from the navbar,
  included on every page, even though the result can only ever flip
  0->1 once (docs/15's first-account-only design) and then stays flipped
  for the rest of the process's life. Added `_registration_closed_cache`,
  a module-level bool that latches `True` the first time a render observes
  an account, skipping the query on every render after that. Integrated
  into the same area 16-6 already touched (`register_form` now shares the
  same `_registration_open()` helper instead of its own separate
  `count_users()` check). See `app/main.py`. Test:
  `tests/test_auth_routes.py::test_registration_open_caches_once_closed`.

- **16-21 — `data/` base dir is an implicit relative-path coupling to the
  volume mount.** **Implemented.** Nothing actually enforced that
  `Storage`'s default `base_dir` ("data") and fly.toml's mount destination
  (`/srv/data`) agreed with each other -- they only did because the
  Dockerfile's `WORKDIR` and the mount destination happened to match. A
  future change to either could silently fall back to ephemeral storage
  with no error. `Storage.__init__` now reads `DATA_DIR` from the
  environment (still defaulting to `"data"` when unset, so local dev is
  unchanged), and fly.toml sets it to the mount path explicitly. See
  `app/storage/storage.py`, `fly.toml`. Tests: `tests/test_storage.py`
  (new file).

- **16-22 — `CORSMiddleware` still uses `allow_origins=["*"]`.**
  **Implemented (comment only, no behavior change, as the finding
  suggested).** Not currently exploitable -- `allow_credentials=False`
  plus the session cookie's `same_site="lax"` both independently block a
  credentialed cross-origin request -- but undocumented, so a future edit
  flipping `allow_credentials` to `True` could silently create a real
  hole. Added a comment explaining exactly why the current combination is
  safe and what specifically must not change without re-narrowing
  `allow_origins` first. See `app/main.py`.

- **16-23 — `currentlyDownloading` UI highlight desyncs on queue-length
  deltas.** **Implemented, via the WS-driven fix the finding preferred.**
  It used to be inferred from "did the queue get shorter between polls",
  which breaks if a video is added to the library mid-batch-download and
  shifts what `queue[0]` actually is. The WebSocket `progress` message
  already carries the real `video_id` that's actively downloading;
  `websocket.js`'s handler now sets `currentlyDownloading` directly from
  that instead of leaving it to be inferred, and `queue.js`'s
  length-delta-based guess was removed (the length check that stops
  polling once the queue is empty stays). See `static/js/websocket.js`,
  `static/js/queue.js`.

- **16-24 — Username-enumeration timing side-channel.**
  **Implemented** (the finding flagged this as optional/low-value given
  the single-account scope, but it was cheap enough to just close):
  `verify_password` previously only ran at all when `get_user()` found a
  row, so an unknown username returned measurably faster than a known
  username with a wrong password. Login now runs a real PBKDF2
  verification against a fixed dummy hash on the unknown-username path
  too, so both paths cost the same. See `app/main.py`'s
  `_DUMMY_PASSWORD_HASH`.

- **16-25 — Three low-priority smells.** **Mixed: two fixed lightly, one
  deferred with reasoning, as the finding allowed.**
  - `_download_in_progress` stuck-forever edge case: **fixed**. Wrapped
    the `asyncio.get_running_loop()` + `background_tasks.add_task()` pair
    in try/except that releases the guard on any exception, so a failure
    to actually schedule the background task can't leave every future
    `/api/download` wedged behind a 409 forever. See
    `app/api/routes.py::start_download`. Test:
    `tests/test_download_task.py::test_start_download_releases_guard_if_scheduling_fails`.
  - Synchronous PBKDF2 blocking the event loop: **fixed**. `login_submit`
    and `register_submit` now run `hash_password`/`verify_password` via
    `asyncio.to_thread` instead of calling them directly, so the ~50-150ms
    of CPU-bound hashing per login/register no longer stalls the whole
    process's single event loop (WS broadcasts, other requests) for that
    duration. See `app/main.py`.
  - Blocking `threading.Lock()` held inside async route handlers:
    **deferred, with reasoning documented in place** (not fixed) --
    both `app/api/routes.py`'s `_download_lock` and
    `app/storage/db.py`'s `Database._lock` are acquired from *both* an
    async route handler (event-loop thread) *and* a plain sync function
    that FastAPI's `BackgroundTasks` runs in a worker thread, so they
    genuinely cross threads; `asyncio.Lock` is explicitly not thread-safe
    and would be actively wrong here, not just a style swap. The
    event-loop stall itself is real but negligible -- every critical
    section under either lock is a handful of attribute reads or sqlite3
    calls with no I/O, not comparable to the multi-second network/disk
    I/O the rest of this app already does per request. See the comments
    left at both `_lock` declarations.

- **16-26 — README changelog entry.** **Implemented.** Added an
  "Unreleased" changelog section summarizing both passes. See `README.md`.
