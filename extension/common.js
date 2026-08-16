// Shared constants for the extension -- imported (via <script> tag / classic
// importScripts, no bundler here, matching the rest of this app's
// no-build-step JS -- see static/js/*.js) by both background.js and
// popup/popup.js. content.js doesn't need these directly: it never talks to
// the API itself, it only asks background.js to (see content.js's own
// comment on why).
const API_BASE_URL = "https://yt-mp3-downloader.fly.dev";
const LOGIN_URL = `${API_BASE_URL}/login`;
