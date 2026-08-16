// One-off, manually-run live test for the extension's on-page thumbnail
// badges (see extension/README.md's "Thumbnail badges" section and this
// feature's task description). Not part of `make e2e` -- like
// extension_live_test.js, this hits the real deployed app
// (https://yt-mp3-downloader.fly.dev) and real youtube.com with real admin
// credentials, on purpose: the point is proving the badge/status/toast flow
// works against production, not a local approximation of it.
//
// Run with: LIVE_ADMIN_USERNAME=... LIVE_ADMIN_PASSWORD=... node extension_badges_live_test.js
//
// Credentials are read from the environment on purpose -- never hardcode a
// real credential into a committed file (see extension_live_test.js's own
// comment on why this matters here specifically).
//
// Cleans up after itself: anything added to the live queue during the test
// is removed via the Undo button (or DELETE /api/library/{video_id} as a
// fallback) before exiting. Never triggers /api/download.
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const os = require('os');

const EXTENSION_PATH = path.resolve(__dirname, '..', '..', 'extension');
const APP_URL = 'https://yt-mp3-downloader.fly.dev';
const USERNAME = process.env.LIVE_ADMIN_USERNAME;
const PASSWORD = process.env.LIVE_ADMIN_PASSWORD;
if (!USERNAME || !PASSWORD) {
  console.error('Set LIVE_ADMIN_USERNAME and LIVE_ADMIN_PASSWORD in the environment before running this script.');
  process.exit(1);
}

// A generic, high-result-count query -- picked so the search results page
// reliably has plenty of thumbnails to badge, without depending on any one
// video staying up long-term.
const SEARCH_QUERY = 'lofi hip hop radio';

async function launchExtensionContext(label) {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), `yt-mp3-badges-${label}-`));
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    args: [
      `--disable-extensions-except=${EXTENSION_PATH}`,
      `--load-extension=${EXTENSION_PATH}`,
    ],
  });
  return context;
}

async function loginFirstParty(page) {
  await page.goto(`${APP_URL}/login`);
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
  console.log('Logged in, current URL:', page.url());
}

async function cleanupViaApi(page, videoId) {
  if (!videoId) return;
  console.log(`\nFallback cleanup: DELETE /api/library/${videoId}`);
  const resp = await page.request.delete(`${APP_URL}/api/library/${videoId}`);
  console.log('Cleanup response status:', resp.status());
}

(async () => {
  const context = await launchExtensionContext('badges');
  let addedVideoId = null;

  try {
    const page = await context.newPage();

    const consoleErrors = [];
    page.on('pageerror', (e) => consoleErrors.push(String(e)));
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('401')) consoleErrors.push(msg.text());
    });

    await loginFirstParty(page);

    // Snapshot library state before the test, to identify which badges
    // should plausibly show "downloaded" (via /api/downloaded) vs
    // "queued" (via /api/library) on this real account.
    const libraryBefore = await (await page.request.get(`${APP_URL}/api/library`)).json();
    const downloadedBefore = await (await page.request.get(`${APP_URL}/api/downloaded?limit=500`)).json();
    console.log(`Account state before test: ${libraryBefore.library.length} queued, ${downloadedBefore.total} downloaded (history).`);

    // --- Search results page ---
    console.log('\n=== Navigating to YouTube search results ===');
    await page.goto(`https://www.youtube.com/results?search_query=${encodeURIComponent(SEARCH_QUERY)}`, {
      waitUntil: 'domcontentloaded',
    });

    // Give the debounced MutationObserver scan + batched /api/statuses call
    // time to run (SCAN_DEBOUNCE_MS=350ms in thumbnail_badges.js, plus
    // network round-trip).
    await page.waitForTimeout(5000);

    const totalBadges = await page.locator('.ytmp3-badge').count();
    const newBadges = await page.locator('.ytmp3-badge--new').count();
    const queuedBadges = await page.locator('.ytmp3-badge--queued').count();
    const downloadedBadges = await page.locator('.ytmp3-badge--downloaded').count();
    console.log(`Badges rendered on search results: ${totalBadges} total (${newBadges} new, ${queuedBadges} queued, ${downloadedBadges} downloaded)`);

    if (totalBadges === 0) {
      throw new Error('Expected at least one thumbnail badge to render on the search results page');
    }
    if (newBadges === 0) {
      throw new Error('Expected at least one "new" badge among ambient search results');
    }

    // Confirm no Shorts thumbnails got badged.
    const shortsHrefBadged = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('.ytmp3-badge')).some((badge) => {
        const anchor = badge.closest('a[href]') || badge.parentElement?.closest('a[href]');
        return anchor && anchor.getAttribute('href')?.includes('/shorts/');
      });
    });
    console.log('Any Shorts thumbnail incorrectly badged:', shortsHrefBadged);
    if (shortsHrefBadged) {
      throw new Error('A Shorts thumbnail was badged -- Shorts are explicitly out of scope');
    }

    // --- Click a "new" badge ---
    console.log('\n=== Clicking a "new" badge ===');
    const firstNewBadge = page.locator('.ytmp3-badge--new').first();
    // Capture which video this is, for cleanup + assertions, before clicking.
    const clickedVideoId = await firstNewBadge.evaluate((badge) => {
      const anchor = badge.closest('a[href]');
      const href = anchor ? anchor.getAttribute('href') : null;
      const match = href && href.match(/[?&]v=([^&]+)/);
      return match ? match[1] : null;
    });
    console.log('Clicking badge for video ID:', clickedVideoId);

    await firstNewBadge.click();

    // Badge should flip to queued in place.
    await page.waitForFunction(
      (vid) => {
        const badges = document.querySelectorAll(`.ytmp3-badge[data-status]`);
        for (const b of badges) {
          const anchor = b.closest('a[href]');
          if (anchor && anchor.getAttribute('href')?.includes(`v=${vid}`)) {
            return b.classList.contains('ytmp3-badge--queued');
          }
        }
        return false;
      },
      clickedVideoId,
      { timeout: 15000 }
    );
    console.log('Confirmed: badge flipped to "queued" in place after click.');
    addedVideoId = clickedVideoId;

    // Toast should appear with title + Undo button.
    const toast = page.locator('.ytmp3-toast').first();
    await toast.waitFor({ state: 'visible', timeout: 5000 });
    const toastText = await toast.locator('.ytmp3-toast__title').textContent();
    console.log('Toast text:', toastText);
    const undoVisible = await toast.locator('.ytmp3-toast__undo').isVisible();
    console.log('Undo button visible:', undoVisible);
    if (!undoVisible) {
      throw new Error('Expected an Undo button on the toast');
    }

    // Confirm server-side the video is genuinely queued now (not just an
    // optimistic UI state).
    const libraryAfterAdd = await (await page.request.get(`${APP_URL}/api/library`)).json();
    const presentAfterAdd = libraryAfterAdd.library.some((v) => v.video_id === clickedVideoId);
    console.log('Video present in live library after badge click:', presentAfterAdd);
    if (!presentAfterAdd) {
      throw new Error('Video was not actually present in the live library after clicking the "new" badge');
    }

    // --- Click Undo ---
    console.log('\n=== Clicking Undo ===');
    await toast.locator('.ytmp3-toast__undo').click();

    await page.waitForFunction(
      () => document.querySelectorAll('.ytmp3-toast').length === 0,
      null,
      { timeout: 5000 }
    );
    console.log('Toast dismissed after Undo.');

    await page.waitForFunction(
      (vid) => {
        const badges = document.querySelectorAll(`.ytmp3-badge[data-status]`);
        for (const b of badges) {
          const anchor = b.closest('a[href]');
          if (anchor && anchor.getAttribute('href')?.includes(`v=${vid}`)) {
            return b.classList.contains('ytmp3-badge--new');
          }
        }
        return false;
      },
      clickedVideoId,
      { timeout: 5000 }
    );
    console.log('Confirmed: badge reverted to "new" after Undo.');

    const libraryAfterUndo = await (await page.request.get(`${APP_URL}/api/library`)).json();
    const presentAfterUndo = libraryAfterUndo.library.some((v) => v.video_id === clickedVideoId);
    console.log('Video present in live library after Undo:', presentAfterUndo);
    if (presentAfterUndo) {
      throw new Error('Video was still present in the live library after clicking Undo');
    }
    addedVideoId = null; // Undo already cleaned it up server-side.

    console.log('\nPage/console errors seen during test:', consoleErrors);
    if (consoleErrors.length > 0) {
      throw new Error(`Unexpected console/page errors during test: ${JSON.stringify(consoleErrors)}`);
    }

    console.log('\nAll badge live tests completed successfully.');
  } finally {
    if (addedVideoId) {
      const page = context.pages()[0] || (await context.newPage());
      await cleanupViaApi(page, addedVideoId);
    }
    await context.close();
  }
})().catch((err) => {
  console.error('LIVE BADGE TEST FAILED:', err);
  process.exit(1);
});
