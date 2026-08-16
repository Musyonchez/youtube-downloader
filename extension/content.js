// Content script for youtube.com/watch and youtube.com/playlist pages
// (see manifest.json's content_scripts). Injects a floating "Send to MP3
// Queue" button rather than splicing into YouTube's own toolbar DOM --
// YouTube's internal class names/structure change often (it's a large,
// frequently-redeployed SPA) and a selector-based injection into it breaks
// silently and often; a fixed-position overlay owned entirely by this
// extension has nothing to break against.
//
// This script never calls the API itself -- see background.js's top
// comment for why. It only reads the current URL and asks background.js
// (via chrome.runtime.sendMessage) to do the actual work, then renders
// whatever state that comes back with.

const BUTTON_ID = "yt-mp3-queue-floating-button";

let currentUrl = null;
let currentAbortToken = 0; // Bumped on every navigation to ignore stale in-flight responses.

function getPageKind() {
  if (location.pathname === "/watch") return "video";
  if (location.pathname === "/playlist") return "playlist";
  return null;
}

// The backend classifies any URL with a `list=` query param as a playlist
// URL (app/services/search.py's validate_url) and /api/video-info actively
// rejects those -- YouTube "watch" pages reached from inside a playlist
// carry `&list=...` themselves, so the video URL sent to the backend has to
// be reconstructed with just `v=`, not window.location.href verbatim.
function canonicalVideoUrl() {
  const videoId = new URLSearchParams(location.search).get("v");
  if (!videoId) return null;
  return `https://www.youtube.com/watch?v=${videoId}`;
}

function canonicalPlaylistUrl() {
  const listId = new URLSearchParams(location.search).get("list");
  if (!listId) return null;
  return `https://www.youtube.com/playlist?list=${listId}`;
}

function removeButton() {
  document.getElementById(BUTTON_ID)?.remove();
}

function ensureButton() {
  let button = document.getElementById(BUTTON_ID);
  if (button) return button;

  button = document.createElement("button");
  button.id = BUTTON_ID;
  button.type = "button";
  document.body.appendChild(button);
  return button;
}

function setButtonState(button, { label, variant, disabled, onClick }) {
  button.textContent = label;
  button.disabled = Boolean(disabled);
  button.className = variant ? `yt-mp3-btn yt-mp3-btn--${variant}` : "yt-mp3-btn";
  button.onclick = onClick || null;
}

function openLoginTab() {
  chrome.runtime.sendMessage({ type: "OPEN_LOGIN_TAB" });
}

async function handleVideoPage(button, url, token) {
  setButtonState(button, { label: "Checking…", variant: "loading", disabled: true });

  const result = await chrome.runtime.sendMessage({ type: "GET_VIDEO_INFO", url });
  if (token !== currentAbortToken) return; // Navigated away while this was in flight.

  if (!result.ok) {
    if (result.status === 401) {
      setButtonState(button, {
        label: "Not logged in — click to log in",
        variant: "warn",
        onClick: openLoginTab,
      });
    } else {
      setButtonState(button, { label: "Couldn't check video", variant: "warn", onClick: () => handleVideoPage(button, url, currentAbortToken) });
    }
    return;
  }

  const video = result.data;
  if (video.status === "queued") {
    setButtonState(button, { label: "Already queued", variant: "queued", disabled: true });
    return;
  }
  if (video.status === "downloaded") {
    setButtonState(button, { label: "Already downloaded", variant: "downloaded", disabled: true });
    return;
  }

  setButtonState(button, {
    label: "Send to MP3 Queue",
    variant: "primary",
    onClick: () => addVideo(button, video, token),
  });
}

async function addVideo(button, video, token) {
  setButtonState(button, { label: "Adding…", variant: "loading", disabled: true });

  const result = await chrome.runtime.sendMessage({ type: "ADD_TO_LIBRARY", video });
  if (token !== currentAbortToken) return;

  if (!result.ok) {
    if (result.status === 401) {
      setButtonState(button, { label: "Not logged in — click to log in", variant: "warn", onClick: openLoginTab });
    } else {
      setButtonState(button, { label: "Failed — retry", variant: "warn", onClick: () => addVideo(button, video, token) });
    }
    return;
  }

  setButtonState(button, { label: "Added! ✓", variant: "success", disabled: true });
}

async function handlePlaylistPage(button, url, token) {
  setButtonState(button, { label: "Checking playlist…", variant: "loading", disabled: true });

  const result = await chrome.runtime.sendMessage({ type: "GET_PLAYLIST_INFO", url });
  if (token !== currentAbortToken) return;

  if (!result.ok) {
    if (result.status === 401) {
      setButtonState(button, { label: "Not logged in — click to log in", variant: "warn", onClick: openLoginTab });
    } else {
      setButtonState(button, {
        label: "Couldn't load playlist",
        variant: "warn",
        onClick: () => handlePlaylistPage(button, url, currentAbortToken),
      });
    }
    return;
  }

  const { videos, summary } = result.data;
  if (summary.new === 0) {
    setButtonState(button, { label: "All videos already queued/downloaded", variant: "queued", disabled: true });
    return;
  }

  setButtonState(button, {
    label: `Send ${summary.new} new video${summary.new === 1 ? "" : "s"} to Queue`,
    variant: "primary",
    onClick: () => addPlaylist(button, videos, token),
  });
}

async function addPlaylist(button, videos, token) {
  setButtonState(button, { label: "Adding…", variant: "loading", disabled: true });

  const result = await chrome.runtime.sendMessage({ type: "ADD_ALL_NEW_FROM_PLAYLIST", videos });
  if (token !== currentAbortToken) return;

  if (result.unauthorized) {
    setButtonState(button, { label: "Not logged in — click to log in", variant: "warn", onClick: openLoginTab });
    return;
  }

  const label = result.failed > 0
    ? `Added ${result.added}, ${result.failed} failed`
    : `Added ${result.added}! ✓`;
  setButtonState(button, { label, variant: result.failed > 0 ? "warn" : "success", disabled: true });
}

function refresh() {
  const kind = getPageKind();
  const token = ++currentAbortToken;

  if (kind === "video") {
    const url = canonicalVideoUrl();
    if (!url) {
      removeButton();
      return;
    }
    const button = ensureButton();
    handleVideoPage(button, url, token);
  } else if (kind === "playlist") {
    const url = canonicalPlaylistUrl();
    if (!url) {
      removeButton();
      return;
    }
    const button = ensureButton();
    handlePlaylistPage(button, url, token);
  } else {
    removeButton();
  }
}

function maybeRefreshOnUrlChange() {
  if (location.href === currentUrl) return;
  currentUrl = location.href;
  refresh();
}

// YouTube is a single-page app -- navigating between videos/playlists does
// NOT reload the page, so a one-shot injection at document_idle would only
// ever render the button for whichever page the content script happened to
// load on. `yt-navigate-finish` is YouTube's own custom event fired after
// its client-side router finishes a navigation; it's the primary signal.
// A MutationObserver on <title> is a fallback for the (rare, but not
// impossible given how often YouTube's frontend changes) case where that
// event doesn't fire for some navigation path -- title text reliably
// changes on every real navigation, and observing it is cheap.
window.addEventListener("yt-navigate-finish", maybeRefreshOnUrlChange);

const titleObserver = new MutationObserver(maybeRefreshOnUrlChange);
const titleEl = document.querySelector("title");
if (titleEl) {
  titleObserver.observe(titleEl, { childList: true });
}

maybeRefreshOnUrlChange();
