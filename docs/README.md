# Docs

Every doc gets a `01-`, `02-`, etc. prefix, except this `README.md` (which stays unprefixed as the folder index).

- [01-audit.md](01-audit.md) — full-repo audit (2026-08-02): correctness, security, dead code, tooling gaps.
- [02-fixes.md](02-fixes.md) — concrete fixes for each audit finding, with suggested order.
- [03-full-improvement-plan.md](03-full-improvement-plan.md) — full-scope improvement plan (backend, frontend, tooling), tracked as a checklist.
- [04-file-reorg.md](04-file-reorg.md) — restructured into an `app/` package + `data/` folder; before/after layout, rationale, and what had to change to make it work.
- [05-browser-verification.md](05-browser-verification.md) — headless-browser verification of the live app; caught and fixed a real search-breaking regression, plus a process gap (no browser testing in CI) left for later.
