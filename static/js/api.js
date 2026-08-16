// API Calls
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(endpoint, options);

    if (!response.ok) {
        // A session that logged out elsewhere or just expired makes every
        // subsequent /api/* call 401 forever (docs/16, 16-14) -- without
        // this, loadStatus()/loadQueue()'s poll loops just console.error
        // and keep polling, leaving the UI frozen (e.g. stuck on
        // "Downloading...") with no visible explanation. Centralized here
        // (rather than in each caller) so every apiCall site gets it,
        // including the poll loops in queue.js.
        if (response.status === 401) {
            window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
            // The redirect above tears down this page; throw anyway so
            // callers mid-await don't act on a response that was never
            // actually successful (e.g. don't render as if data came back).
            throw new Error('Session expired -- redirecting to login.');
        }
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
    }

    return await response.json();
}

// Load Status
async function loadStatus() {
    try {
        const data = await apiCall('/api/status');
        document.getElementById('queue-count').textContent = data.library_count;
        document.getElementById('downloaded-count').textContent = data.downloaded_count;

        // Enable/disable buttons
        const hasQueue = data.library_count > 0;
        document.getElementById('download-btn').disabled = !hasQueue;
        document.getElementById('clear-btn').disabled = !hasQueue;
    } catch (error) {
        console.error('Failed to load status:', error);
    }
}

// Load Queue
async function loadQueue() {
    try {
        const data = await apiCall('/api/library');
        queue = data.library;
        console.log('Queue loaded:', queue.length, 'items');
        renderQueue();
    } catch (error) {
        console.error('Failed to load queue:', error);
    }
}

// Load Config
async function loadConfig() {
    try {
        config = await apiCall('/api/config');
        document.getElementById('audio-quality').value = config.audio_quality;
        document.getElementById('download-dir').value = config.download_dir;
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

// Load Fly-sync availability and show/hide the "Sync from Fly" button
// accordingly (local-only feature, only offered when FLY_SYNC_URL/
// FLY_SYNC_USERNAME/FLY_SYNC_PASSWORD are all configured -- see
// app/api/routes.py's /api/sync/status). Failing closed (button stays
// hidden) on any error, same as the other loadX() functions here.
async function loadSyncStatus() {
    const btn = document.getElementById('sync-btn');
    if (!btn) return;
    try {
        const data = await apiCall('/api/sync/status');
        btn.style.display = data.available ? '' : 'none';
    } catch (error) {
        console.error('Failed to load sync status:', error);
        btn.style.display = 'none';
    }
}
