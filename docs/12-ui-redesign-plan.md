# 12 — UI Redesign Plan: New Palette + CSS-Only Design Pass

Turns [11-ui-aesthetic-findings.md](11-ui-aesthetic-findings.md) into a
scoped, sequenced implementation task. Per that doc's own risk assessment,
this pass deliberately stays in the **CSS-only, low-risk tier** (agent 3's
steps 1-4) — no card/queue-item/navbar markup changes, no JS-coupled work.
That's not a scope-cut on the palette itself (the user explicitly asked for
a genuinely strong new palette, not a token tweak) — it's a scope-cut on
*where else* to spend effort this pass, per docs/11's own conservative
recommendation for a single-user utility tool.

## Creative direction: "warm analog"

The current palette (`#6366f1` indigo → `#7c3aed` violet → `#d946ef`
fuchsia) is a generic, extremely recognizable default-SaaS gradient —
confirmed independently by all 3 audit agents. Replacing it with a
*different* generic default (another blue, another purple, a Spotify-like
green, a YouTube-like red) would just swap one cliché for another.

New direction: lean into what this app actually is — a personal
**music** tool — instead of looking like every other AI-generated
dashboard. Reference point: vintage audio equipment. VU meters, tube-amp
glow, brass/copper hardware, vinyl warmth. Concretely:

- **Primary accent — warm copper/amber.** Dominant, used the way the old
  indigo was (buttons, active states, focus rings, logo) but as one true
  "brand" color rather than diluted across a 3-stop gradient.
- **Secondary accent — deep teal.** A genuinely different hue (not a
  shade of the primary) used sparingly for a second layer of hierarchy —
  specifically to replace the arbitrary `--queued: #2563eb` blue, so the
  "queued" status badge ties back into the app's own palette instead of
  being an unrelated color no other part of the UI uses.
- Both chosen to read as intentional in *both* themes, unlike the current
  accent which is dark-mode-only by omission (see scope item 3 below).

This is a **principle** ("commit to a warm, audio-domain-appropriate
dominant color + one genuinely distinct sharp accent"), not a demand for
one specific hex from me — the implementing agent should pick/tune the
exact values and verify contrast computationally (WCAG AA, both themes,
both as button-background-with-white-text and as text-on-background),
the same way the AUD-15 badge-contrast fix in docs/09 did.

## Scope for this pass

Directly addresses docs/11 Agent 2's top findings #1 (typography), #2
(gradient reused everywhere), #7 (light mode is a mechanical inversion),
and the disconnect between status colors and brand color. Follows Agent
3's recommended sequencing, steps 1-4:

1. **Consolidate the duplicate `:root` token blocks** (`app.css:3-24` /
   `landing.css:3-19` are currently identical, copy-pasted) into one
   shared `static/css/variables.css`, loaded the same way `nav.css`
   already is. Value-preserving at this step — a pure mechanical
   extraction before any values change, so the palette swap in step 3 is
   a one-file edit instead of two.
2. **New palette values**, in the consolidated file:
   - `--accent`, `--accent-hover` → copper/amber family.
   - New `--accent-secondary` → deep teal, replacing the arbitrary
     `--queued` blue (`app.css:18`) — same color, better name/purpose.
   - `--gradient-1` → two-stop copper→amber (not a 3-stop rainbow;
     agent 2's finding was that the *reuse count* is the problem, not
     gradients per se — keep it to one clean, restrained gradient used
     only where it already is, not spread further).
   - Sync the hardcoded `rgba(99, 102, 241, ...)` glow/shadow tints in
     `landing.css` (lines flagged in docs/11 agent 1: 126,131,207,213,
     367,471,623,628) and `app.css:124` to the new accent numerically —
     these don't derive from the CSS variable, so they'd silently keep
     the old indigo glow otherwise.
   - `--success-strong`/`--warning-strong` (added in the earlier audit
     pass, docs/09 AUD-15) can stay — they're semantic status colors, not
     part of the generic-SaaS problem; only `--queued`'s arbitrary blue
     gets replaced.
3. **Fill in the missing light-theme overrides** (docs/11 agent 3
   gotcha #1): `[data-theme="light"]` currently redefines backgrounds/
   text/border but silently inherits the dark-mode `--accent`,
   `--gradient-1`, and status colors. Explicitly decide and set light-mode
   values for all of these as part of the palette work, not as an
   afterthought — verify contrast against a *white* background
   specifically, which the dark-mode values were never tuned for.
4. **Typography** — load one distinctive heading font (not
   Inter/Roboto/Arial/system, not Space Grotesk — docs/10 flags all of
   those as overused-by-AI), applied to headings only (`h1`/`h2`/
   `.search-header h1`/logo text). Body copy stays on the system stack
   (agent 1's own recommendation — scan-speed matters on a phone over
   LAN, and body text isn't where the "generic" signal lives). Loaded via
   a single Google Fonts `<link>` in `head_extras.html`, matching the
   zero-build-tooling constraint agent 3 confirmed.
5. **Add `prefers-reduced-motion` support project-wide** — confirmed by
   agent 3 to not exist anywhere currently. Cheap, real accessibility gap,
   worth doing alongside a visual pass rather than as a separate future
   task. A simple media query disabling/shortening the existing
   `@keyframes` (shimmer, pulse, slideIn, etc.) and the landing page's
   `IntersectionObserver`-driven fade-ins.

## Explicitly NOT in this pass (deferred, tracked in docs/11)

Per docs/11's own risk tiering — these are JS-coupled, higher-risk, or
low-value-for-a-single-user-tool:

- Replacing the fake browser-mockup hero visual (real screenshot / actual
  product content) — content work, not styling, separate task.
- Landing-page page-load motion choreography — worth doing, but only
  after step 5's reduced-motion guard exists as its own change, and it's
  optional/low-priority per agent 1 (no real audience for this page).
- De-formularizing the landing page's section rhythm (redundant feature/
  use-case grids, all-centered headers) — structural HTML work.
- Unifying `createVideoCard()`/`createHistoryCard()` — recommended by
  agent 3 as a prerequisite *before* any card markup redesign, but no
  card markup redesign is happening in this pass, so it's not blocking.
- Any card/queue-item/navbar structural markup change — agent 3's
  highest-risk tier, explicitly recommended last and only with full
  manual re-verification.

## Verification requirements

Same bar as every prior pass in this repo: full check suite (pytest is
unaffected — this is CSS/template only, but flake8/ruff/mypy should still
pass since `head_extras.html`/templates change), then live browser
verification via Playwright in **both themes** and **both nav
breakpoints** (768px landing / 968px app, per docs/11 agent 3's gotcha
about independently-duplicated breakpoints), checking:

- Contrast (WCAG AA) for the new accent/secondary/gradient values against
  both the dark and light background, computed not eyeballed.
- The `--queued` → `--accent-secondary` rename doesn't break the
  `.status-badge.queued` styling added in docs/09 (AUD-06).
- No visual regression in the compact view / skeleton loaders / toasts
  that reference the old token names.
- `prefers-reduced-motion: reduce` actually suppresses the relevant
  animations (can be verified via Playwright's
  `page.emulateMedia({ reducedMotion: 'reduce' })`).

## Delegation

Given the volume of file touches (both CSS files, `head_extras.html`, a
new `variables.css`) but the contained, CSS-only nature of the work
(per docs/11's own "no new tooling, no JS coupling" verdict for this
tier), this is being delegated to an implementation agent rather than
done inline, to keep this session's context free for review/verification
rather than raw file editing. The agent's brief is the "Creative
direction" and "Scope" sections above verbatim.
