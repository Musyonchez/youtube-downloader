# 13 — UI Redesign Phase 2: Closing Out docs/11's Deferred Items

[12-ui-redesign-plan.md](12-ui-redesign-plan.md) deliberately stayed
CSS-only (palette/typography/motion-guard). This phase finishes the rest
of [11-ui-aesthetic-findings.md](11-ui-aesthetic-findings.md)'s findings
and agent 3's higher-risk/JS-coupled tier, now that the palette/font
foundation is in place to build on.

## Scope

### Track A — Card-builder unification (prerequisite, do first)

`static/js/search.js`'s `createVideoCard()` and `static/js/history.js`'s
`createHistoryCard()` are two independent, near-duplicate DOM-builder
functions (docs/11 agent 3's top structural-risk finding). Unify them into
one shared builder (e.g. `static/js/cards.js`, loaded like the other
shared scripts) that both call, parameterized for their differences
(status badge text/class, action button — "Add to Queue" vs "Retry",
presence of a date line). This must happen *before* any card visual
changes below, or those changes have to be made twice and will drift
(exactly the bug class docs/06 already fixed once for the navbar).

While in this code, also address docs/11 agent 2 finding #8: differentiate
the *functional* app/history card language from the *marketing*
landing-page card language (feature-card/use-case-card) — they currently
share one flat-bordered-box-with-hover-lift recipe. The app/history cards
should stay information-dense and low-noise (their job is fast scanning of
a queue/library); the differentiation belongs on the landing side (Track
B), not by making functional cards fancier.

Run the existing `tests/e2e/search.spec.js` after this change — its
selectors (`.video-card`, `.add-to-queue-btn`, etc.) must still resolve.

### Track B — Landing page: real identity, not a template

Addresses docs/11 agent 2 findings #3, #4, #5, #6:

1. **Replace the fake browser-mockup hero visual** (`index.html`'s
   `.mockup-window` with 4 gray pulsing placeholder rectangles). Show
   something that actually represents the product: realistic-looking
   video card content (real-ish thumbnail treatment, title, channel,
   duration — styled to look like an actual search result, not an empty
   box) and/or a music-domain visual motif (see #3 below) worked into the
   hero rather than a generic "browser chrome" frame.
2. **One deliberate page-load motion moment.** Currently there's no hero
   entrance animation at all (content just appears), while every
   below-the-fold section gets an identical scroll-triggered fade-up
   applied uniformly. Add a staggered hero reveal (headline → subtext →
   CTA → mockup, offset timing) as the one orchestrated "moment," per
   docs/10's own framing (one high-impact moment > scattered uniform
   micro-interactions). Must respect `prefers-reduced-motion` (the guard
   added in docs/12 — reuse it, don't add a second mechanism).
3. **Add one consistent audio/music-domain visual motif.** A waveform
   accent (e.g. a subtle animated or static waveform bar pattern) used
   somewhere it'll actually be seen repeatedly — e.g. behind/around the
   hero mockup, as a loading-state visual, or as a small recurring
   graphic element — so the app reads as a music tool specifically. Right
   now the only audio-domain visual in the entire codebase is the emoji
   favicon.
4. **De-formularize the section rhythm.** Currently: hero → 3-col feature
   grid → alternating steps → 3-col use-case grid (near-duplicate card
   recipe of the feature grid) → FAQ accordion → CTA, every section header
   centered. Collapse the redundant features/use-cases grids into one
   differentiated section (they currently repeat the same card recipe for
   different content), and break the all-centered-header pattern in at
   least one section (e.g. left-align a section header, or break a grid
   out of the container width).

Do not touch `app.html`/`history.html` in this track — this is landing-page-only.

## Explicitly still out of scope

- No changes to the 70/30 app-page split, queue-panel behavior, or
  settings modal — those are functionally correct and not part of any
  aesthetic finding.
- No new build tooling (confirmed unnecessary by docs/11 agent 3).
- No changes to backend/API code — this phase is templates/CSS/JS only.

## Verification requirements (same bar as every prior pass)

- Full check suite: pytest, flake8, ruff, mypy.
- Live Playwright verification in both themes, both nav breakpoints
  (768px landing / 968px app), `prefers-reduced-motion` respected, zero
  console errors.
- Explicitly re-verify `tests/e2e/search.spec.js` passes after Track A's
  refactor (its selectors depend on card markup staying compatible).
- Explicitly re-verify the `.status-badge`/`.status-badge.queued`
  distinction (docs/09 AUD-06) and the History page's Retry button (docs/09
  AUD-26) still work after Track A unifies the card builders.

## Delegation

Tracks A and B touch largely disjoint files (A: `search.js`, `history.js`,
a new `cards.js`, `app.css`/`history.css` card rules; B: `index.html`,
`landing.css`, `landing.js`) and are being run as two parallel
implementation agents for that reason. Track A's shared-builder file must
land in a form Track B doesn't need to know about (B doesn't touch
app/history cards at all). Each agent verifies its own track; a final
integration check (full suite + one more Playwright pass) happens after
both land.
