# Docs

Every doc gets a `01-`, `02-`, etc. prefix, except this `README.md` (which stays unprefixed as the folder index).

- [01-audit.md](01-audit.md) — full-repo audit (2026-08-02): correctness, security, dead code, tooling gaps.
- [02-fixes.md](02-fixes.md) — concrete fixes for each audit finding, with suggested order.
- [03-full-improvement-plan.md](03-full-improvement-plan.md) — full-scope improvement plan (backend, frontend, tooling), tracked as a checklist.
- [04-file-reorg.md](04-file-reorg.md) — restructured into an `app/` package + `data/` folder; before/after layout, rationale, and what had to change to make it work.
- [05-browser-verification.md](05-browser-verification.md) — headless-browser verification of the live app; caught and fixed a real search-breaking regression, plus a process gap (no browser testing in CI) left for later.
- [06-ui-review.md](06-ui-review.md) — full frontend review: navbar duplicated across pages (headline finding, unified into a shared partial), theme-flash/FOUC, dead links, and other polish.
- [07-ffmpeg-conversion-bug.md](07-ffmpeg-conversion-bug.md) — downloaded files turned out to be raw WebM, not MP3: FFmpeg was never installed on this machine, and failed conversions left orphaned raw files with no extension. Fixed and installed FFmpeg.
- [08-comprehensive-audit-prompt.md](08-comprehensive-audit-prompt.md) — reusable multi-agent audit playbook, adapted to this project's actual shape (single-user, LAN-only, no auth). Re-run for future full-repo passes.
- [09-comprehensive-audit-findings.md](09-comprehensive-audit-findings.md) — results of running 08's playbook: 6 parallel agents (architecture, bugs, UI/UX, backend/data, security/perf, testing/DX). Headline finding: failed downloads vanished with no record or retry path. Fixed the P1/P2 cluster; P3/P4 tracked for later.
- [10-claude-skills-for-ui-ux.md](10-claude-skills-for-ui-ux.md) — portable reference notes (not project-specific): what Claude Skills are, a catalog of 8 UI/UX-focused skills, a finding on principle-based vs. prescriptive skill design, and a Claude Design product walkthrough.
