# Post-Auth Audit Findings

## How this doc came to exist

This doc was supposed to already exist, with findings 16-1 through 16-26,
before implementation started -- that's the normal order (see docs/08/09's
"audit first, modify later" ground rule, and how docs/11 -> docs/12/13
worked). It didn't: no commit on `master`, any branch, or any worktree ever
added it. There is no lost draft to recover -- it was never written.

Given that, this pass reconstructed and implemented only the findings for
which enough concrete detail existed to act on responsibly (file:line-level
specifics supplied alongside the implementation task itself, covering 16
of the 26 IDs below). The remaining 10 IDs (16-10, 16-12, 16-14, 16-15,
16-16, 16-21 through 16-25) are listed as **not reconstructed** --
inventing plausible-sounding security/behavior findings for them under
real-looking IDs would be worse than leaving the gap explicit. If a real
audit produced those findings, they should be transcribed in here directly
(with real file:line evidence) rather than re-derived from scratch.

## Findings

Each finding below is marked **Implemented** with what changed, or **Not
reconstructed** for the ones with no available source material.

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

### P4 / Future

- **16-26 — README changelog entry.** **Implemented.** Added an
  "Unreleased" changelog section summarizing this pass. See `README.md`.

- **16-10, 16-12, 16-14, 16-15, 16-16, 16-21 through 16-25.**
  **Not reconstructed** -- no source material (file:line evidence, impact,
  recommended fix) was available for these IDs anywhere in the repo or
  its history. Left as gaps rather than invented. If/when a real audit
  produces these findings, they belong here with genuine evidence.
