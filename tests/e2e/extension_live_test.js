// One-off, manually-run live test for the Chrome extension's CORS/cookie
// mechanism (see extension/README.md's "Testing" section). Not part of
// `make e2e` (that suite runs against a local mocked-search dev server,
// docs/05) -- this hits the real deployed app at
// https://yt-mp3-downloader.fly.dev with real admin credentials, on
// purpose, because the whole point is proving the cross-origin credentialed
// cookie mechanism works against production CORS config, not a local
// approximation of it.
//
// Run with: LIVE_ADMIN_USERNAME=... LIVE_ADMIN_PASSWORD=... node extension_live_test.js
//
// Credentials are read from the environment on purpose -- this script hits
// the real production account, and a real credential must never be
// hardcoded into a committed file (a hardcoded admin password was
// committed here once during this feature's development, caught by
// GitGuardian, and the exposed password was rotated immediately; don't
// repeat that mistake).
//
// Cleans up after itself: anything added to the live queue during the test
// is removed via DELETE /api/library/{video_id} before exiting. Never
// triggers /api/download.
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
// youtube.com/watch?v=jNQXAC9IVRw -- "Me at the zoo", the first video ever
// uploaded to YouTube (2005). About as stable/unlikely-to-disappear as a
// public YouTube video gets.
const VIDEO_ID = 'jNQXAC9IVRw';
const VIDEO_URL = `https://www.youtube.com/watch?v=${VIDEO_ID}`;

async function launchExtensionContext(label) {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), `yt-mp3-ext-${label}-`));
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    args: [
      `--disable-extensions-except=${EXTENSION_PATH}`,
      `--load-extension=${EXTENSION_PATH}`,
    ],
  });
  return context;
}

async function getServiceWorker(context) {
  let [sw] = context.serviceWorkers();
  if (!sw) {
    sw = await context.waitForEvent('serviceworker', { timeout: 15000 });
  }
  return sw;
}

async function waitForButtonState(page, predicate, timeoutMs = 20000) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    last = await page.locator('#yt-mp3-queue-floating-button').textContent().catch(() => '');
    if (predicate(last)) return last;
    await page.waitForTimeout(400);
  }
  throw new Error(`Timed out waiting for button state; last text was: "${last}"`);
}

async function testLoggedIn() {
  console.log('\n=== Logged-in context ===');
  const context = await launchExtensionContext('loggedin');
  const page = await context.newPage();
  let addedVideoId = null;

  // First, delete any leftover queue entry from a previous run (idempotent
  // setup, not the test's own cleanup).
  await page.goto(`${APP_URL}/login`);
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
  console.log('Logged in, current URL:', page.url());
  await page.request.delete(`${APP_URL}/api/library/${VIDEO_ID}`).catch(() => {});

  const sw = await getServiceWorker(context);
  console.log('Service worker URL:', sw.url());

  const swRequests = [];
  sw.on('request', (req) => {
    if (req.url().startsWith(APP_URL)) swRequests.push(`${req.method()} ${req.url()}`);
  });
  sw.on('response', (res) => {
    if (res.url().startsWith(APP_URL)) console.log(`  [SW] <- ${res.status()} ${res.url()}`);
  });

  await page.goto(VIDEO_URL, { waitUntil: 'domcontentloaded' });

  const readyText = await waitForButtonState(
    page,
    (t) => t && !t.includes('Checking') && !t.includes('Adding'),
    20000
  );
  console.log('Floating button text (ready):', readyText);

  if (!readyText.includes('Send to MP3 Queue')) {
    throw new Error(`Expected "Send to MP3 Queue" (video should be fresh after cleanup above), got: "${readyText}"`);
  }

  await page.click('#yt-mp3-queue-floating-button');
  const afterText = await waitForButtonState(page, (t) => t && !t.includes('Adding'), 20000);
  console.log('Floating button text after click:', afterText);
  if (!afterText.includes('Added')) {
    throw new Error(`Expected "Added! ✓" after clicking, got: "${afterText}"`);
  }
  addedVideoId = VIDEO_ID;

  console.log('Requests seen from service worker to the app:', swRequests);

  // Confirm via a direct authenticated first-party request whether the
  // video is now in the library -- proves the extension's add actually
  // landed server-side, not just that the UI optimistically said so.
  const libraryResp = await page.request.get(`${APP_URL}/api/library`);
  const library = await libraryResp.json();
  const inLibrary = library.library.some((v) => v.video_id === VIDEO_ID);
  console.log('Video present in live library after test:', inLibrary);
  if (!inLibrary) {
    throw new Error('Video was not actually present in the live library after the extension "added" it');
  }

  return { context, page, addedVideoId };
}

async function cleanup(page, videoId) {
  if (!videoId) return;
  console.log(`\nCleaning up: DELETE /api/library/${videoId}`);
  const resp = await page.request.delete(`${APP_URL}/api/library/${videoId}`);
  console.log('Cleanup response status:', resp.status());
  const libraryResp = await page.request.get(`${APP_URL}/api/library`);
  const library = await libraryResp.json();
  const stillThere = library.library.some((v) => v.video_id === videoId);
  console.log('Video still in library after cleanup:', stillThere);
}

async function testLoggedOut() {
  console.log('\n=== Logged-out (fresh) context ===');
  const context = await launchExtensionContext('loggedout');
  try {
    const page = await context.newPage();
    await page.goto(VIDEO_URL, { waitUntil: 'domcontentloaded' });

    const text = await waitForButtonState(page, (t) => t && !t.includes('Checking'), 20000);
    console.log('Floating button text (should indicate not logged in):', text);
    if (!text.includes('Not logged in')) {
      throw new Error(`Expected "Not logged in" state, got: "${text}"`);
    }

    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      page.click('#yt-mp3-queue-floating-button'),
    ]);
    await newPage.waitForLoadState();
    console.log('URL opened on click:', newPage.url());
    if (!newPage.url().includes('/login')) {
      throw new Error(`Expected click to open /login, got ${newPage.url()}`);
    }
    console.log('Confirmed: not-logged-in click opens /login as expected.');
  } finally {
    await context.close();
  }
}

(async () => {
  let loggedInResult;
  try {
    loggedInResult = await testLoggedIn();
    await testLoggedOut();
  } finally {
    if (loggedInResult) {
      await cleanup(loggedInResult.page, loggedInResult.addedVideoId);
      await loggedInResult.context.close();
    }
  }
  console.log('\nAll live extension tests completed successfully.');
})().catch((err) => {
  console.error('LIVE TEST FAILED:', err);
  process.exit(1);
});
