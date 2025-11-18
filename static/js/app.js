// YouTube MP3 Downloader - Frontend JavaScript

// State
let searchResults = [];
let selectedVideos = new Set();
let queue = [];
let config = {};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadStatus();
    await loadQueue();
    await loadConfig();
    setupWebSocket();
});

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

// Search
async function handleSearch() {
    const input = document.getElementById('search-input').value.trim();
    if (!input) {
        showToast('Please enter a search query or URL', 'error');
        return;
    }

    const searchType = document.querySelector('input[name="search-type"]:checked').value;

    try {
        if (searchType === 'name') {
            await searchByName(input);
        } else if (searchType === 'url') {
            await searchByUrl(input);
        } else if (searchType === 'playlist') {
            await searchByPlaylist(input);
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function searchByName(query) {
    const data = await apiCall('/api/search', 'POST', { query, limit: 15 });
    searchResults = data.results;
    renderResults();
}

async function searchByUrl(url) {
    const data = await apiCall('/api/video-info', 'POST', { url });
    searchResults = [data];
    renderResults();
}

async function searchByPlaylist(url) {
    const data = await apiCall('/api/playlist-info', 'POST', { url });
    searchResults = data.videos;
    renderResults();
    showToast(`Found ${data.summary.total} videos (${data.summary.new} new)`, 'success');
}

// Render Results
function renderResults() {
    const grid = document.getElementById('results-grid');

    if (searchResults.length === 0) {
        grid.innerHTML = '<p class="placeholder">No results found</p>';
        return;
    }

    grid.innerHTML = '';

    searchResults.forEach(video => {
        const card = createVideoCard(video, true);
        grid.appendChild(card);
    });

    updateAddButton();
}

// Render Queue
function renderQueue() {
    const grid = document.getElementById('queue-grid');

    if (queue.length === 0) {
        grid.innerHTML = '<p class="placeholder">Queue is empty</p>';
        return;
    }

    grid.innerHTML = '';

    queue.forEach(video => {
        const card = createVideoCard(video, false);
        grid.appendChild(card);
    });
}

// Create Video Card
function createVideoCard(video, isResult = true) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.dataset.videoId = video.video_id;

    if (video.status === 'downloaded') {
        card.classList.add('downloaded');
    }

    // Thumbnail
    const thumbnailContainer = document.createElement('div');
    thumbnailContainer.className = 'thumbnail-container';

    const thumbnail = document.createElement('img');
    thumbnail.className = 'thumbnail';
    thumbnail.alt = video.title;
    thumbnail.loading = 'lazy';

    // Only add error handler if we have a thumbnail URL
    if (video.thumbnail) {
        thumbnail.src = video.thumbnail;

        // Fallback if thumbnail fails to load
        thumbnail.onerror = function() {
            this.style.display = 'none';
            // Add a placeholder background to the container
            thumbnailContainer.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            thumbnailContainer.style.display = 'flex';
            thumbnailContainer.style.alignItems = 'center';
            thumbnailContainer.style.justifyContent = 'center';

            // Add music icon as fallback
            const icon = document.createElement('div');
            icon.style.fontSize = '48px';
            icon.textContent = '🎵';
            thumbnailContainer.insertBefore(icon, thumbnailContainer.firstChild);
        };
    } else {
        // No thumbnail URL provided, show placeholder
        thumbnail.style.display = 'none';
        thumbnailContainer.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        thumbnailContainer.style.display = 'flex';
        thumbnailContainer.style.alignItems = 'center';
        thumbnailContainer.style.justifyContent = 'center';

        const icon = document.createElement('div');
        icon.style.fontSize = '48px';
        icon.textContent = '🎵';
        thumbnailContainer.insertBefore(icon, thumbnailContainer.firstChild);
    }

    const durationBadge = document.createElement('div');
    durationBadge.className = 'duration-badge';
    durationBadge.textContent = video.duration;

    thumbnailContainer.appendChild(thumbnail);
    thumbnailContainer.appendChild(durationBadge);

    // Status badge
    if (video.status && video.status !== 'new') {
        const statusBadge = document.createElement('div');
        statusBadge.className = `status-badge ${video.status}`;
        statusBadge.textContent = video.status === 'downloaded' ? '✓' : '📥';
        thumbnailContainer.appendChild(statusBadge);
    }

    // Info
    const info = document.createElement('div');
    info.className = 'video-info';

    const title = document.createElement('div');
    title.className = 'video-title';
    title.textContent = video.title;
    title.title = video.title;

    const channel = document.createElement('div');
    channel.className = 'video-channel';
    channel.textContent = video.channel;

    info.appendChild(title);
    info.appendChild(channel);

    card.appendChild(thumbnailContainer);
    card.appendChild(info);

    // Click handler
    if (isResult) {
        if (video.status === 'new') {
            card.onclick = () => toggleSelection(video);
        } else {
            card.style.cursor = 'not-allowed';
        }
    } else {
        card.onclick = () => removeFromQueue(video.video_id);
    }

    return card;
}

// Toggle Selection
function toggleSelection(video) {
    const videoId = video.video_id;

    if (selectedVideos.has(videoId)) {
        selectedVideos.delete(videoId);
    } else {
        selectedVideos.add(videoId);
    }

    // Update UI
    const card = document.querySelector(`[data-video-id="${videoId}"]`);
    if (card) {
        card.classList.toggle('selected');
    }

    updateAddButton();
}

// Update Add Button
function updateAddButton() {
    const btn = document.getElementById('add-selected-btn');

    if (selectedVideos.size > 0) {
        btn.classList.remove('hidden');
        btn.textContent = `Add ${selectedVideos.size} to Queue`;
    } else {
        btn.classList.add('hidden');
    }
}

// Add Selected to Queue
async function addSelectedToQueue() {
    const videos = searchResults.filter(v => selectedVideos.has(v.video_id));

    if (videos.length === 0) {
        return;
    }

    try {
        const data = await apiCall('/api/library/add-multiple', 'POST', videos);
        showToast(`Added ${data.added} videos to queue`, 'success');

        selectedVideos.clear();
        await loadStatus();
        await loadQueue();
        renderResults(); // Re-render to update status
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Remove from Queue
async function removeFromQueue(videoId) {
    if (!confirm('Remove this video from queue?')) {
        return;
    }

    try {
        await apiCall(`/api/library/${videoId}`, 'DELETE');
        showToast('Removed from queue', 'success');
        await loadStatus();
        await loadQueue();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Clear Queue
async function clearQueue() {
    if (!confirm('Clear entire queue?')) {
        return;
    }

    try {
        await apiCall('/api/library', 'DELETE');
        showToast('Queue cleared', 'success');
        await loadStatus();
        await loadQueue();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Download Queue
async function downloadQueue() {
    try {
        const data = await apiCall('/api/download', 'POST');
        showToast(data.message, 'success');
        showDownloadProgress();

        // Poll for updates
        const interval = setInterval(async () => {
            await loadStatus();
            await loadQueue();

            if (queue.length === 0) {
                clearInterval(interval);
                hideDownloadProgress();
                showToast('All downloads complete!', 'success');
            }
        }, 2000);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Settings
function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    panel.classList.toggle('hidden');
}

async function saveSettings() {
    const audioQuality = document.getElementById('audio-quality').value;
    const downloadDir = document.getElementById('download-dir').value;

    try {
        await apiCall('/api/config', 'POST', {
            audio_quality: audioQuality,
            download_dir: downloadDir
        });
        showToast('Settings saved', 'success');
        await loadConfig();
        toggleSettings();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Download Progress UI
function showDownloadProgress() {
    const progress = document.getElementById('download-progress');
    progress.classList.remove('hidden');
}

function hideDownloadProgress() {
    const progress = document.getElementById('download-progress');
    progress.classList.add('hidden');
}

function updateProgress(percent, text) {
    document.getElementById('progress-fill').style.width = `${percent}%`;
    document.getElementById('progress-text').textContent = text;
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// WebSocket
function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // Handle real-time updates here
        console.log('WebSocket message:', data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Enter key for search
function handleSearchEnter(event) {
    if (event.key === 'Enter') {
        handleSearch();
    }
}
