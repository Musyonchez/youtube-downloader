// Background service worker (Manifest V3) -- the only place in this
// extension that talks to the deployed app's API. content.js (running on
// youtube.com) and popup.js both go through here via chrome.runtime
// messaging rather than calling fetch() themselves, for two reasons:
//
//   1. A fetch() issued from a youtube.com content script would carry
//      youtube.com's own cookies/origin, not the extension's -- it has
//      nothing to do with this extension's chrome-extension://<id> origin
//      that the backend's CORS allowlist actually trusts (see app/main.py
//      and extension/README.md). The request has to originate from the
//      extension's own context (this service worker, or the popup) for
//      `Origin: chrome-extension://<id>` to be what the browser sends.
//   2. Centralizing it here means there's exactly one place that knows the
//      API's base URL and auth-failure handling, instead of duplicating
//      that in both content.js and popup.js.
importScripts("common.js");

// Empirically verified (see extension/README.md's "Cookie mechanism"
// section for how this was tested against the live deployed app):
// fetch(url, {credentials: 'include'}) from this MV3 service worker DOES
// carry the SameSite=Lax session cookie on a cross-origin request to the
// backend, once the backend's CORS allowlist explicitly trusts this
// extension's origin (app/main.py's EXTENSION_ORIGIN) with
// allow_credentials=True. That's the whole mechanism -- no
// chrome.cookies/declarativeNetRequest cookie-injection fallback was
// needed. Chrome's SameSite=Lax enforcement is about the request's
// *initiator site* vs. the *target site*; a request whose initiator is a
// chrome-extension:// origin isn't a "cross-site" web request in the sense
// SameSite=Lax exists to block (there's no attacker-controlled web page
// initiating it), so Chrome does not withhold the cookie here the way it
// would for e.g. https://evil.example fetching this same URL.
async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (response.status === 401) {
    return { ok: false, status: 401, data: null };
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // No JSON body (e.g. a 204) -- fine, callers that need data check `ok`.
  }

  if (!response.ok) {
    return { ok: false, status: response.status, data };
  }

  return { ok: true, status: response.status, data };
}

async function checkAuth() {
  const result = await apiFetch("/api/status");
  return { loggedIn: result.ok };
}

async function getVideoInfo(url) {
  return apiFetch("/api/video-info", { method: "POST", body: JSON.stringify({ url }) });
}

async function getPlaylistInfo(url) {
  return apiFetch("/api/playlist-info", { method: "POST", body: JSON.stringify({ url }) });
}

async function addToLibrary(video) {
  return apiFetch("/api/library/add", { method: "POST", body: JSON.stringify(video) });
}

// Adds every 'new'-status video from a playlist-info response, skipping
// already-queued/already-downloaded ones -- mirrors static/js's own
// playlist-add semantics (search.js's searchByPlaylist +
// queue.js's addSingleToQueue, one call per new video) rather than
// inventing a bulk-add endpoint that doesn't exist on the backend.
async function addAllNewFromPlaylist(videos) {
  let added = 0;
  let failed = 0;
  for (const video of videos) {
    if (video.status !== "new") continue;
    const result = await addToLibrary(video);
    if (result.ok) {
      added += 1;
    } else if (result.status === 401) {
      // Stop immediately -- every subsequent add would also 401, and the
      // caller needs to distinguish "session expired mid-run" from "some
      // videos failed for other reasons".
      return { added, failed, unauthorized: true };
    } else {
      failed += 1;
    }
  }
  return { added, failed, unauthorized: false };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    switch (message.type) {
      case "CHECK_AUTH":
        sendResponse(await checkAuth());
        break;
      case "GET_VIDEO_INFO":
        sendResponse(await getVideoInfo(message.url));
        break;
      case "GET_PLAYLIST_INFO":
        sendResponse(await getPlaylistInfo(message.url));
        break;
      case "ADD_TO_LIBRARY":
        sendResponse(await addToLibrary(message.video));
        break;
      case "ADD_ALL_NEW_FROM_PLAYLIST":
        sendResponse(await addAllNewFromPlaylist(message.videos));
        break;
      case "OPEN_LOGIN_TAB":
        chrome.tabs.create({ url: LOGIN_URL });
        sendResponse({ ok: true });
        break;
      default:
        sendResponse({ ok: false, error: `Unknown message type: ${message.type}` });
    }
  })();
  return true; // Keep the message channel open for the async sendResponse above.
});
