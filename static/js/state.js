// Shared state -- read and mutated by the other app.js modules. Loaded first
// (plain scripts sharing global scope, no bundler) so these are declared
// before anything else references them.
let searchResults = [];
let queue = [];
let config = {};
let queueCollapsed = false;
let isDownloading = false;
let currentlyDownloading = null; // Track which video is currently downloading
let currentView = 'grid'; // Track current view mode
let resultsFilter = 'all'; // 'all' | 'downloaded' | 'not-downloaded'

// video_id -> true/false, populated by websocket.js's download_complete handler.
// Read (and cleared) by downloadSingle() in queue.js so it reports the real
// outcome instead of assuming success once an item leaves the queue.
let downloadOutcomes = {};

// Pagination
const ITEMS_PER_PAGE = 20;
let currentPage = 1;
