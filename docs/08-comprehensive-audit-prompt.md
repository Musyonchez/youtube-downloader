# Comprehensive Multi-Agent Project Audit — Playbook

A reusable prompt for running a deep, multi-perspective audit of this repo with
specialized subagents. Adapted from a generic template to fit this project's
actual shape (see "Project context" below) so agents don't waste effort
auditing things that don't apply here (multi-tenancy, horizontal scaling,
i18n, etc.) -- auth/session handling *does* apply now (docs/15, docs/16),
see "Project context" below.

Re-run this whenever the project has grown enough since the last audit
([01-audit.md](01-audit.md)) to justify another full pass.

---

## Project context (read this before auditing)

- **What it is:** a personal, single-account FastAPI web app for searching
  YouTube and downloading audio as tagged MP3s, deployed publicly on
  Fly.io. Not a multi-tenant SaaS product, but **not unauthenticated
  either** (docs/16, 16-11 corrected this section -- it previously said
  "no login system... not a gap to re-flag", which was true when this doc
  was written for a LAN-only deployment and stopped being true once the
  app went public): real session-cookie login/register/logout (docs/15),
  first-account-only registration enforced server-side, PBKDF2 password
  hashing, and a pure-ASGI middleware gating every route except the
  landing page and the auth pages themselves. Auth/session handling is
  back in scope for future audits -- don't skip it.
- **Stack:** FastAPI + Jinja2 templates, plain `<script>` tag JS (no bundler,
  no framework, global scope shared across `static/js/*.js` — deliberate),
  SQLite (stdlib `sqlite3`) for library/download state, JSON for config,
  yt-dlp for extraction, mutagen for ID3 tagging, WebSockets for live
  progress, Playwright for e2e/browser verification.
- **Layout:** `app/` package (`api/`, `services/`, `storage/`), `data/`
  (config.json + downloads.db, gitignored), `static/`, `templates/`
  (+ `partials/`), `tests/` (+ `tests/e2e/`), `docs/`, `scripts/`.
- **Prior audits already covered:** file/folder reorganization
  ([04](04-file-reorg.md)), navbar/FOUC/UI consistency ([06](06-ui-review.md)),
  a search-breaking validation bug and browser-verification gap
  ([05](05-browser-verification.md)), an FFmpeg conversion data-integrity bug
  ([07](07-ffmpeg-conversion-bug.md)). Don't re-report these unless new
  evidence shows they regressed.
- **Out of scope by design, do not re-flag:** multi-tenancy (single
  account by design, docs/15), horizontal scaling, i18n. CSRF risk is
  reduced (not eliminated) by `same_site="lax"` session cookies -- still
  worth a look on any audit that touches auth/session handling.

---

## Ground rules

1. **Audit first, modify later.** No production code changes during the
   audit unless explicitly instructed afterward — findings must stay
   reproducible.
2. **Inspect the actual code.** Don't assume something is broken (or fine)
   without reading it. Trace frontend → route → service → storage where
   relevant.
3. **Evidence required.** Every meaningful finding needs: category,
   severity, file path (+ line/function where possible), what's wrong,
   why it matters, a concrete fix, and a confidence level (confirmed /
   likely / possible / smell).
4. **No vague claims.** Not "the architecture could be improved" — instead
   "`X` does A/B/C and couples to `Y`; move B into `Z`."
5. **Distinguish objective bugs/gaps from subjective taste.** Flag taste
   calls as such.
6. **Don't over-engineer.** No framework/library swaps, no rewrites, no
   abstractions for one-off code, unless a concrete problem justifies it.
7. **Call out what's good, too.** The point is triage, not a hit list —
   note decisions that should stay as-is.
8. **Avoid duplicate findings** across agents — merge at consolidation,
   keep evidence from each contributor, identify the shared root cause.

---

## Phase 1 — Discovery

Before specialized audits start, get oriented: read `docs/README.md` and the
prior audit docs, skim the package layout, note what looks unfinished vs.
intentional. This can be done by the orchestrator; specialized agents don't
each need to re-derive it from scratch.

## Phase 2 — Specialized audits (parallel, non-overlapping scope)

Run these as separate agents. Each owns a distinct slice so work doesn't
duplicate:

- **A — Architecture & Code Quality:** package/module boundaries, coupling
  between `app/api`/`app/services`/`app/storage`, duplication, dead code,
  dead routes, naming, the shared-global-scope JS pattern (is it still
  holding up as `static/js/*.js` grows?), technical debt.
- **B — Bugs & Reliability:** logic errors, edge cases, async/WebSocket
  race conditions, error handling, null/empty handling, download-queue
  state transitions, retry/failure paths, incorrect status transitions
  (queued/downloading/downloaded/new).
- **C — UI/UX, Accessibility & Responsive:** visual/interaction review of
  `templates/*.html` + `static/css/*`, consistency across landing vs. app
  pages, empty/loading/error states, keyboard navigation, focus states,
  ARIA/semantic HTML, contrast, mobile/tablet layout (queue panel, navbar,
  filter toggle, pagination).
- **D — Backend/API & Data Integrity:** `app/api/routes.py` validation and
  status codes, `app/services/*` correctness vs. what the frontend assumes,
  `app/storage/db.py` schema/constraints/indexes, WAL-mode concurrency
  correctness, what happens on partial failures (mirrors the FFmpeg bug
  class — look for other places a failed operation could leave orphaned
  state on disk or in the DB).
- **E — Security & Performance:** input validation/sanitization on
  user-supplied URLs/queries, path handling for downloaded filenames
  (path traversal via sanitize_filename), secrets/config handling, error
  message leakage, dependency versions; plus perf — large-library search
  performance (currently 650+ downloads), N+1-style DB queries, thumbnail
  loading, bundle/asset size, WebSocket message volume.
- **F — Testing, Product Gaps & DX:** what's covered in `tests/` vs. the
  highest-value missing tests (specify exactly what and why, not "add more
  tests"); incomplete-feeling workflows or missing functionality relative
  to the app's actual purpose (not generic SaaS features); README/setup
  accuracy for a fresh clone (`run.sh`/`run.ps1`, FFmpeg prerequisite,
  `.env`/config setup).

## Phase 3 — Cross-check

A synthesis pass reviews all findings together, looking specifically for:

- Contradictions between agents
- The same root cause reported from multiple angles (merge these)
- Interactions between individually-fine decisions that combine into a
  real problem
- "What would still surprise a real user of this app that no single audit
  caught?"

## Phase 4 — Consolidation & severity

Use this severity scale:

| Severity | Meaning |
|---|---|
| P0 — Critical | Breaks core functionality, causes data loss/corruption, or is a real security hole for the publicly-deployed, session-auth-gated surface |
| P1 — High | Real bug, real UX problem, or real architectural pain that should be fixed soon |
| P2 — Medium | Worth doing, not urgent |
| P3 — Low | Polish / cleanup |
| P4 — Nice-to-have | Optional, low impact |

Produce a master issue table:

| ID | Severity | Area | Finding | Evidence (file:line) | Impact | Recommended Fix | Effort | Confidence |
|----|----------|------|---------|----------------------|--------|------------------|--------|------------|

## Phase 5 — Deliverable

Write the findings to the next-numbered `docs/NN-*.md` file (per the
project's doc-numbering convention — see `docs/README.md`), structured as:

1. Executive summary (health, top strengths, top risks, top 10 priorities)
2. Findings by area (architecture, bugs, UI/UX/a11y, backend/data,
   security/perf, testing/gaps/DX)
3. Master issue table
4. What's already good / don't touch
5. Roadmap: Immediate → Soon → Later → Future, noting dependencies between
   fixes

Then add the new doc to `docs/README.md`'s index line-list, matching the
existing one-line-per-doc style.

Do **not** start implementing fixes as part of this pass — that's a
separate, explicitly-requested follow-up (matching the pattern used for
every prior audit in this repo: findings doc first, fix doc/implementation
second).
