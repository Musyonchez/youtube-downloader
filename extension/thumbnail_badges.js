// Thumbnail status badges -- runs on every youtube.com page (see
// manifest.json's now-broadened content_scripts match), unlike content.js's
// floating button which only renders on /watch and /playlist. This is the
// "don't have to open a video to queue it" feature: a small badge in the
// top-left corner of every video thumbnail YouTube renders (home feed,
// search results, channel pages, sidebars/related, subscriptions, playlist
// listings), showing new/queued/downloaded, with the "new" badge itself
// queueing the video on click.
//
// Same division of labor as content.js: this script never calls the API
// directly, it only reads YouTube's own rendered DOM and asks background.js
// (via chrome.runtime.sendMessage) to do the actual work -- see
// background.js's top comment for why (CORS origin has to be the
// extension's, not youtube.com's).
//
// YouTube's frontend genuinely changes its DOM structure over time (see
// extension/README.md's own note on this for content.js's floating button).
// Live inspection while building this (2026-08) found YouTube mid-migration
// between two renderer generations on the *same* site: search results still
// use the older `ytd-video-renderer` / `ytd-thumbnail` structure, while
// channel grids and the watch-page related-videos sidebar have moved to a
// newer `yt-lockup-view-model` / `yt-thumbnail-view-model` structure (often
// nested *inside* `ytd-rich-item-renderer` on grid layouts, but standalone
// on the sidebar). CONTAINER_SELECTOR below lists both generations plus the
// tag names named in this feature's task description
// (ytd-compact-video-renderer, ytd-grid-video-renderer,
// ytd-playlist-video-renderer) even though live inspection didn't turn up
// examples of those on the pages checked -- harmless to keep as selectors,
// and they may still appear on layouts/locales/experiments not checked.

const CONTAINER_SELECTOR = [
  "ytd-rich-item-renderer",
  "ytd-video-renderer",
  "ytd-compact-video-renderer",
  "ytd-grid-video-renderer",
  "ytd-playlist-video-renderer",
  "yt-lockup-view-model",
].join(", ");

// Belt-and-suspenders Shorts exclusion. The real defense is that
// findThumbnailAnchor() below only ever accepts an `/watch?`-href anchor --
// a Shorts thumbnail's anchor is `/shorts/<id>`, so it's structurally
// invisible to that check regardless of which wrapper tag surrounds it.
// This closest() check just skips known Shorts containers early, before
// even looking for an anchor, to avoid doing pointless work on them.
const SHORTS_ANCESTOR_SELECTOR = [
  "ytd-reel-item-renderer",
  "ytd-reel-shelf-renderer",
  "ytd-reel-video-renderer",
  "ytm-shorts-lockup-view-model",
].join(", ");

const BADGE_REGISTERED_ATTR = "data-ytmp3-registered";
const SCAN_DEBOUNCE_MS = 350;
const STATUSES_BATCH_MAX = 200; // Matches StatusesRequest's Field(max_length=200) on the backend.
const TOAST_DURATION_MS = 10000;
const MAX_TOASTS = 5;
const TOAST_CONTAINER_ID = "yt-mp3-toast-container";

// videoId -> "new" | "queued" | "downloaded", populated by /api/statuses
// responses and updated optimistically by this script's own add/undo
// actions. Never re-fetched on a timer -- only extended (new ids) or
// corrected in place (actions this extension itself takes).
const statusCache = new Map();

// videoId -> Set of {hostEl, videoId, meta, badgeEl} -- the same video can
// appear multiple times on one page (e.g. in the grid AND the sidebar), so
// a status change has to fan out to every rendered badge for that id.
const videoBadgeMap = new Map();

// videoIds seen this scan window that aren't in statusCache yet -- flushed
// as one or more batched /api/statuses calls after the debounce window.
const pendingIds = new Set();

let scanDebounceTimer = null;

function extractVideoId(href) {
  if (!href) return null;
  let url;
  try {
    url = new URL(href, location.origin);
  } catch {
    return null;
  }
  if (url.pathname !== "/watch") return null; // Excludes /shorts/<id> and anything else.
  return url.searchParams.get("v");
}

function findThumbnailAnchor(container) {
  for (const a of container.querySelectorAll("a[href]")) {
    const href = a.getAttribute("href") || "";
    if (href.startsWith("/watch?") || href.startsWith("https://www.youtube.com/watch?")) {
      return a;
    }
  }
  return null;
}

// The element the badge is actually positioned against -- prefer a tight
// image-only wrapper over the whole anchor (which on the newer lockup
// structure can include extra hover/touch-feedback layers) so the badge
// visually sits on the thumbnail image itself, not floating over
// surrounding chrome.
function findThumbHost(anchor) {
  return anchor.querySelector("yt-thumbnail-view-model") || anchor.closest("ytd-thumbnail") || anchor;
}

function firstNonEmptyText(container, selector) {
  for (const el of container.querySelectorAll(selector)) {
    const text = el.textContent.trim();
    if (text) return text;
  }
  return "";
}

// Scrapes whatever YouTube has already rendered for this thumbnail --
// deliberately never a real API call (there can be hundreds of these on one
// page; /api/video-info is yt-dlp-backed and far too slow/heavy to call per
// thumbnail). Every field falls back to "" rather than throwing if YouTube's
// markup doesn't match any known selector (e.g. duration is genuinely absent
// for some live streams) -- VideoItem's schema already accepts empty
// strings for these fields (see app/api/routes.py's VideoItem).
function extractMeta(container, anchor) {
  const titleEl = container.querySelector(
    "#video-title, #video-title-link, .ytLockupMetadataViewModelTitle, yt-formatted-string#video-title"
  );
  const title = titleEl ? titleEl.textContent.trim() : (anchor.getAttribute("aria-label") || "").trim();

  const channelEl = container.querySelector(
    "ytd-channel-name #text, #channel-name #text, ytd-channel-name a, .yt-content-metadata-view-model-wiz__metadata-text, .ytLockupMetadataViewModelByline"
  );
  const channel = channelEl ? channelEl.textContent.trim() : "";

  // Covers both renderer generations' time-overlay badge (see this file's
  // top comment) -- old-style `.ytd-thumbnail-overlay-time-status-renderer`
  // and new-style `badge-shape`/`.ytBadgeShapeText`.
  const duration = firstNonEmptyText(
    container,
    ".ytd-thumbnail-overlay-time-status-renderer, .ytBadgeShapeText, badge-shape"
  );

  const imgEl = anchor.querySelector("img") || container.querySelector("img");
  const thumbnail = imgEl ? imgEl.getAttribute("src") || imgEl.getAttribute("data-thumb") || "" : "";

  return { title, channel, duration, thumbnail };
}

function ensureBadgeElement(entry) {
  if (entry.badgeEl) return entry.badgeEl;

  const host = entry.hostEl;
  if (getComputedStyle(host).position === "static") {
    host.style.position = "relative";
  }

  const badge = document.createElement("button");
  badge.type = "button";
  badge.className = "ytmp3-badge";
  host.appendChild(badge);
  entry.badgeEl = badge;
  return badge;
}

function updateBadgeVisual(entry, status) {
  const badge = ensureBadgeElement(entry);
  badge.dataset.status = status;
  badge.className = `ytmp3-badge ytmp3-badge--${status}`;

  if (status === "downloaded") {
    badge.textContent = "✓"; // check
    badge.title = "Already downloaded";
    badge.onclick = null;
  } else if (status === "queued") {
    badge.textContent = "⏳"; // hourglass
    badge.title = "Already queued";
    badge.onclick = null;
  } else {
    badge.textContent = "+";
    badge.title = "Add to MP3 queue";
    badge.onclick = (event) => handleBadgeClick(event, entry);
  }
}

function applyStatusToAllBadges(videoId) {
  const status = statusCache.get(videoId);
  if (!status) return;
  const entries = videoBadgeMap.get(videoId);
  if (!entries) return;
  for (const entry of entries) {
    updateBadgeVisual(entry, status);
  }
}

function registerThumbnail(hostEl, videoId, meta) {
  const entry = { hostEl, videoId, meta, badgeEl: null };
  let entries = videoBadgeMap.get(videoId);
  if (!entries) {
    entries = new Set();
    videoBadgeMap.set(videoId, entries);
  }
  entries.add(entry);

  if (statusCache.has(videoId)) {
    updateBadgeVisual(entry, statusCache.get(videoId));
  } else {
    pendingIds.add(videoId);
  }
}

// YouTube's infinite scroll / SPA navigation constantly adds *and removes*
// thumbnail elements from the DOM (not just adds) -- without this,
// videoBadgeMap would keep growing forever over a long browsing session,
// holding onto detached hostEl/badgeEl references for thumbnails that were
// scrolled away and torn down long ago. Called opportunistically at the
// start of every scan() rather than wired into the MutationObserver's own
// removal records -- cheap (a handful of .isConnected checks per scan, not
// per removed node) and doesn't require tracking which specific nodes were
// removed.
function cleanupVideoBadgeMap() {
  for (const [videoId, entries] of videoBadgeMap) {
    for (const entry of entries) {
      if (!entry.hostEl.isConnected) entries.delete(entry);
    }
    if (entries.size === 0) videoBadgeMap.delete(videoId);
  }
}

function scan() {
  cleanupVideoBadgeMap();

  const containers = document.querySelectorAll(CONTAINER_SELECTOR);

  for (const container of containers) {
    if (container.closest(SHORTS_ANCESTOR_SELECTOR)) continue;

    const anchor = findThumbnailAnchor(container);
    if (!anchor) continue;

    const videoId = extractVideoId(anchor.getAttribute("href"));
    if (!videoId) continue;

    const hostEl = findThumbHost(anchor);
    if (hostEl.hasAttribute(BADGE_REGISTERED_ATTR)) continue;
    hostEl.setAttribute(BADGE_REGISTERED_ATTR, "1");

    registerThumbnail(hostEl, videoId, extractMeta(container, anchor));
  }

  flushPendingStatuses();
}

function flushPendingStatuses() {
  if (pendingIds.size === 0) return;
  const ids = Array.from(pendingIds);
  pendingIds.clear();

  for (let i = 0; i < ids.length; i += STATUSES_BATCH_MAX) {
    resolveStatusChunk(ids.slice(i, i + STATUSES_BATCH_MAX));
  }
}

async function resolveStatusChunk(videoIds) {
  const result = await chrome.runtime.sendMessage({ type: "GET_STATUSES", videoIds });
  // On failure (including 401 -- not logged into the app) badges for these
  // ids are simply left unmounted rather than guessing a status. No
  // re-poll-on-a-timer: if the same id gets seen again in a later scan
  // it'll just re-join pendingIds and get another chance.
  if (!result || !result.ok || !result.data) return;

  for (const [videoId, status] of Object.entries(result.data.statuses)) {
    statusCache.set(videoId, status);
    applyStatusToAllBadges(videoId);
  }
}

function scheduleScan() {
  if (scanDebounceTimer) clearTimeout(scanDebounceTimer);
  scanDebounceTimer = setTimeout(() => {
    scanDebounceTimer = null;
    scan();
  }, SCAN_DEBOUNCE_MS);
}

async function handleBadgeClick(event, entry) {
  event.preventDefault();
  event.stopPropagation();

  const badge = entry.badgeEl;
  if (!badge || badge.dataset.status !== "new") return;

  badge.disabled = true;
  badge.classList.add("ytmp3-badge--loading");

  const video = {
    video_id: entry.videoId,
    title: entry.meta.title,
    channel: entry.meta.channel,
    duration: entry.meta.duration,
    url: `https://www.youtube.com/watch?v=${entry.videoId}`,
    thumbnail: entry.meta.thumbnail,
  };

  const result = await chrome.runtime.sendMessage({ type: "ADD_TO_LIBRARY", video });

  badge.classList.remove("ytmp3-badge--loading");
  badge.disabled = false;

  if (!result.ok) {
    if (result.status === 401) {
      chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB" });
    }
    updateBadgeVisual(entry, "new"); // Stays clickable either way -- nothing was actually queued.
    return;
  }

  statusCache.set(entry.videoId, "queued");
  applyStatusToAllBadges(entry.videoId);
  showToast(entry.videoId, video.title);
}

// --- Toast notifications (bottom-left, stacked up to MAX_TOASTS) ---

let activeToasts = []; // Oldest first.

function ensureToastContainer() {
  let container = document.getElementById(TOAST_CONTAINER_ID);
  if (!container) {
    container = document.createElement("div");
    container.id = TOAST_CONTAINER_ID;
    document.body.appendChild(container);
  }
  return container;
}

function dismissToast(toast) {
  if (toast.timeoutId) clearTimeout(toast.timeoutId);
  toast.el.remove();
  activeToasts = activeToasts.filter((t) => t !== toast);
}

function showToast(videoId, title) {
  // 6th+ toast while 5 are showing: drop the oldest to make room (standard
  // notification-stack behavior), rather than growing unbounded or
  // rejecting the newest.
  while (activeToasts.length >= MAX_TOASTS) {
    dismissToast(activeToasts[0]);
  }

  const container = ensureToastContainer();

  const el = document.createElement("div");
  el.className = "ytmp3-toast";

  const titleEl = document.createElement("span");
  titleEl.className = "ytmp3-toast__title";
  titleEl.textContent = `Queued: ${title || videoId}`;

  const undoBtn = document.createElement("button");
  undoBtn.type = "button";
  undoBtn.className = "ytmp3-toast__undo";
  undoBtn.textContent = "Undo";

  el.appendChild(titleEl);
  el.appendChild(undoBtn);
  container.appendChild(el);

  const toast = { videoId, el, timeoutId: null };
  undoBtn.onclick = () => handleUndo(toast);
  toast.timeoutId = setTimeout(() => dismissToast(toast), TOAST_DURATION_MS);
  activeToasts.push(toast);
}

async function handleUndo(toast) {
  dismissToast(toast);
  const result = await chrome.runtime.sendMessage({ type: "REMOVE_FROM_LIBRARY", videoId: toast.videoId });
  if (result && result.ok) {
    statusCache.set(toast.videoId, "new");
    applyStatusToAllBadges(toast.videoId);
  }
}

// --- Wiring ---

const bodyObserver = new MutationObserver(scheduleScan);
bodyObserver.observe(document.body, { childList: true, subtree: true });

scheduleScan();
