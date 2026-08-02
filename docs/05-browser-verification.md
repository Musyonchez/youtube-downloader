# Browser Verification — 2026-08-03

After the SQLite migration, `app.js` module split, and `app/`+`data/` package reorganization, drove the actual running app with a headless browser (Playwright/Chromium -- `chromium-cli` wasn't available in this environment, so used `npx playwright` directly) rather than just HTTP-level `TestClient` checks. Server launched for real via `python -m app.main`, the actual entry point after the reorg.

## What was checked

- Landing page (`/`), dark and light theme, both before and after scrolling (specifically to confirm the navbar-goes-dark-in-light-mode bug from [03-full-improvement-plan.md](03-full-improvement-plan.md) stays fixed).
- `/app/name`, `/app/playlist`, `/app/url` -- all three search modes.
- A real search-by-name against live YouTube (`lofi hip hop`), confirming search results render with working thumbnails.
- Add-to-queue end-to-end: click → toast → queue panel updates → `/api/status` count updates.
- Settings modal open/render.
- Browser console checked for JS errors on every page (`console --errors` equivalent via Playwright's `console`/`pageerror` events).

Screenshots and captured data confirmed no console errors anywhere except one caught issue (below), and confirmed via direct DOM inspection (`naturalWidth`, `complete`) that thumbnails do load correctly -- an earlier screenshot that looked like blank thumbnails was just a screenshot-timing artifact (lazy-loaded `<img>`s not yet resolved when the shot was taken), not a real bug.

## Found and fixed immediately

**Search-by-name was completely broken in the real UI.** `search.js`'s `searchByName()` sends `limit: 60` (3 pages × 20 items for pagination), but the `SearchRequest` Pydantic model's `Field(le=50)` -- added earlier during the config-validation work -- rejected it with a 422. This was invisible to the existing test suite because nothing tested the actual value the frontend sends; the only limit-related test used an intentionally-too-high value (500) to check the bound existed at all, not whether legitimate values pass. Fixed: bound raised to `le=100`, and `tests/test_api_validation.py` now asserts `limit=60` specifically is accepted (regression test) alongside the existing "excessive value rejected" case.

## Found and fixed (cosmetic)

- **"Search by Url" instead of "Search by URL"** on the URL-mode page. Python's `.title()` on `mode` capitalized `"url"` → `"Url"`, not the acronym `"URL"`. Fixed by having `app/main.py`'s `read_app` route pass an explicit `MODE_LABELS = {"name": "Name", "playlist": "Playlist", "url": "URL"}` lookup as `mode_label` into the template instead of relying on `.title()` in `templates/app.html`. Verified via `TestClient`: `/app/url` now renders "Search by URL" in both the page `<h1>` and `<title>`.

## Left for later (process gap, not a bug)

- **No browser-level testing exists in CI.** The search-limit bug above is exactly the kind of frontend/backend contract mismatch that unit tests and `TestClient`-level HTTP tests structurally can't catch -- they test the API in isolation, never what the actual browser-rendered JS actually sends. `.github/workflows/ci.yml` only runs Python syntax/type/lint/test checks. Consider adding a minimal Playwright smoke test (load `/app/name`, run one real search, assert no console errors and at least one result renders) to CI so this class of bug is caught automatically next time, rather than only when someone happens to manually verify in a browser. Not added in this pass -- it needs a decision on whether CI should be allowed to hit real YouTube over the network (flaky/rate-limit risk) or whether the search would need to be mocked, which is a design choice worth deciding deliberately rather than bolting on.
