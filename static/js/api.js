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
