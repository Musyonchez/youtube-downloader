# UI/Frontend Review — 2026-08-03

Read `templates/index.html`, `templates/app.html`, `static/css/{landing,app}.css`, and `static/js/{landing,ui}.js` in full, cross-checked against the live screenshots from [05-browser-verification.md](05-browser-verification.md). Findings below, in priority order. Implementation status tracked per item.

## 1. The navbar is fully duplicated, not shared (headline finding)

Every page hand-copies its own navbar: HTML markup, CSS rules, and JS behavior all exist twice, independently:

- **HTML**: `index.html` and `app.html` each inline their own `<nav class="navbar">` block (logo, nav links, theme toggle SVGs, mobile menu button) -- word-for-word duplicated SVG markup for the sun/moon icons in three places (`index.html`'s desktop nav, `index.html`'s mobile menu, `app.html`'s desktop nav; `app.html`'s mobile menu even drops the theme toggle entirely -- see finding 5).
- **CSS**: `static/css/landing.css` and `static/css/app.css` each define their own `.navbar`, `.nav-content`, `.logo`, `.logo-text`, `.nav-links a`, `.theme-toggle`, `.mobile-menu-btn`, `.mobile-menu` rules -- with real drift already: `landing.css` styles `.logo` directly (bare text, no link), `app.css` styles `.logo a` (expects the logo to be a link) since only `app.html`'s logo is wrapped in `<a href="/">`.
- **JS**: `toggleTheme`, `updateThemeIcon`, `initTheme`, and `toggleMobileMenu` are defined identically in both `static/js/landing.js` and `static/js/ui.js`.

This isn't hypothetical risk -- it already caused two real bugs found and fixed in this session: the light-theme-navbar-goes-dark-on-scroll bug ([03-full-improvement-plan.md](03-full-improvement-plan.md)) only existed in `landing.js`/`landing.css` because that's the one copy that happened to have the scroll handler; and the "Search by Url" label bug was adjacent nav/template drift. Any future navbar change (add a link, fix an icon, adjust mobile breakpoint) has to be made in two-to-three places by hand, with no mechanism to notice if one is missed.

**Status: implemented.** Extracted a single `templates/partials/navbar.html` Jinja include (parameterized: `active_mode` for highlighting the current search mode, `show_settings` to toggle the settings-gear button that only makes sense on app pages), a shared `static/css/nav.css`, and a shared `static/js/nav.js`. Both pages now include/link all three instead of maintaining their own copies. Removed the now-dead duplicated rules/functions from `landing.css`/`app.css`/`landing.js`/`ui.js`.

## 2. Theme flash (FOUC) on first paint

`app.html` hardcodes `<html lang="en" data-theme="dark">` -- so a user whose stored preference is `light` sees a flash of dark theme before the end-of-body `initTheme()` script runs and flips it. `index.html` has no `data-theme` attribute at all on initial HTML, relying entirely on an IIFE at the top of `landing.js` (loaded at the end of `<body>`) -- same flash, worse (defaults to no theme at all, i.e. whatever the CSS's base/default rules are, until JS runs).

**Status: implemented.** Added a small inline `<script>` in `<head>` (before the stylesheet link) on both pages that synchronously reads `localStorage.getItem('theme')` and sets `data-theme` on `<html>` before first paint -- the standard FOUC-prevention pattern. Removed the hardcoded `data-theme="dark"` default and the `landing.js` IIFE now that the head script handles it.

## 3. External footer links missing `rel="noopener noreferrer"`

`index.html`'s footer links to `yt-dlp` and `FastAPI` use `target="_blank"` without `rel="noopener noreferrer"` -- the linked page can access `window.opener` and repoint the original tab (reverse tabnabbing). Low real-world risk here (linking to well-known open-source project pages, not user content), but it's a one-line fix with no downside.

**Status: implemented.**

## 4. Dead footer links

The footer's "Tech Stack" column (`Python`, `FastAPI`, `yt-dlp`) all link to `href="#"` -- literal no-ops, and redundant with the "Resources" column two spots over which already links to the real yt-dlp/FastAPI sites. Clicking any of the three currently just jumps to the top of the page.

**Status: implemented.** Removed the redundant "Tech Stack" column; it duplicated "Resources" with dead links and added no real content.

## 5. `app.html`'s mobile menu drops the theme toggle

`index.html`'s mobile menu includes a theme-toggle button; `app.html`'s mobile menu (`templates/app.html:56-60` before this change) does not -- on a phone-width `/app/*` page with the menu open, there's no way to switch themes except closing the menu, finding the (hidden-behind-hamburger) desktop toggle, which doesn't exist at that width either. This was a real gap in the app pages specifically, not present on the landing page.

**Status: implemented.** Fixed as a side effect of unifying the navbar partial -- the shared mobile menu now includes the theme toggle on every page.

## 6. Stale copyright year

Footer says "© 2024 YT Downloader" -- hardcoded, wrong (site was built into 2025/2026 per the README changelog).

**Status: implemented.** Rendered dynamically from the server (`datetime.now().year`) via the navbar/footer partial context instead of hardcoded, so it can't go stale again.

## 7. No favicon

Neither page references a favicon; browsers show a generic blank/default tab icon. Minor, but a five-minute fix.

**Status: implemented.** Added a simple inline SVG favicon (musical note emoji-style, matches the "🎵" used throughout the README) via a data URI in the shared `<head>` -- no extra static file/request needed.

## Reviewed, left as-is (not a problem)

- **Color palette (`:root` CSS variables) is duplicated** between `landing.css` and `app.css` but *not* drifted -- both define identical hex values for dark/light themes. Lower risk than the navbar duplication since there's no *behavior* to diverge, just static values. Worth consolidating into a shared `variables.css` at some point, but out of scope for this pass -- flagging here rather than doing it silently, since it touches every color rule in both stylesheets and deserves its own reviewed change.
- **Landing page's marketing sections** (Features, How It Works, Use Cases, FAQ) -- read through fully, no bugs found, copy and structure are coherent and consistent with what the app actually does.
- **No Open Graph / Twitter card meta tags** -- not added; this is a LAN-only personal tool, not meant to be publicly shared/indexed, so social-preview cards have no real audience.
