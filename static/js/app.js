// YouTube MP3 Downloader - Frontend JavaScript

// State
let searchResults = [];
let selectedVideos = new Set();
let queue = [];
let config = {};
let queueCollapsed = false;

// Pagination
const ITEMS_PER_PAGE = 20;
let currentPage = 1;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    await loadStatus();
    await loadQueue();
    await loadConfig();
    updateQueueUI();
    setupWebSocket();
    
    // Check screen size and auto-collapse queue on mobile
    if (window.innerWidth <= 968) {
        queueCollapsed = true;
        document.getElementById('queuePanel')?.classList.add('collapsed');
        document.getElementById('queueFloatBtn')?.classList.add('show');
    }
});

// Theme Management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const sunIcons = document.querySelectorAll('.sun-icon');
    const moonIcons = document.querySelectorAll('.moon-icon');
    
    if (theme === 'light') {
        sunIcons.forEach(icon => icon.style.display = 'none');
        moonIcons.forEach(icon => icon.style.display = 'block');
    } else {
        sunIcons.forEach(icon => icon.style.display = 'block');
        moonIcons.forEach(icon => icon.style.display = 'none');
    }
}

// Initialize theme on page load
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

// Mobile Menu Toggle
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    menu.classList.toggle('active');
}

// Queue Toggle
function toggleQueue() {
    const panel = document.getElementById('queuePanel');
    const floatBtn = document.getElementById('queueFloatBtn');
    
    queueCollapsed = !queueCollapsed;
    
    if (queueCollapsed) {
        panel?.classList.add('collapsed');
        floatBtn?.classList.add('show');
    } else {
        panel?.classList.remove('collapsed');
        floatBtn?.classList.remove('show');
    }
}

// Update Queue UI
function updateQueueUI() {
    const floatBtn = document.getElementById('queueFloatBtn');
    const badge = document.getElementById('queueBadge');
    
    if (floatBtn && badge) {
        if (queue.length > 0) {
            floatBtn.classList.remove('inactive');
            badge.textContent = queue.length;
            badge.classList.remove('hidden');
        } else {
            floatBtn.classList.add('inactive');
            badge.classList.add('hidden');
        }
    }
}

// Settings Modal
function toggleSettings() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.classList.toggle('hidden');
    } else {
        console.error('Settings modal not found');
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('settings-modal');
    if (e.target === modal?.querySelector('.modal-overlay')) {
        toggleSettings();
    }
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

// Create skeleton loader card
function createSkeletonCard() {
    const card = document.createElement('div');
    card.className = 'skeleton-card';
    
    const thumbnail = document.createElement('div');
    thumbnail.className = 'skeleton-thumbnail';
    
    const info = document.createElement('div');
    info.className = 'skeleton-info';
    
    const title1 = document.createElement('div');
    title1.className = 'skeleton-title';
    
    const title2 = document.createElement('div');
    title2.className = 'skeleton-title';
    
    const channel = document.createElement('div');
    channel.className = 'skeleton-channel';
    
    const button = document.createElement('div');
    button.className = 'skeleton-button';
    
    info.appendChild(title1);
    info.appendChild(title2);
    info.appendChild(channel);
    info.appendChild(button);
    
    card.appendChild(thumbnail);
    card.appendChild(info);
    
    return card;
}

// Show skeleton loaders
function showSkeletonLoaders(count = 12) {
    const grid = document.getElementById('results-grid');
    grid.innerHTML = '';
    
    for (let i = 0; i < count; i++) {
        const skeleton = createSkeletonCard();
        grid.appendChild(skeleton);
    }
}

// Loading state
function setSearchLoading(isLoading) {
    const btn = document.getElementById('search-btn');
    const btnText = document.getElementById('search-btn-text');
    const spinner = document.getElementById('search-spinner');
    const input = document.getElementById('search-input');

    if (isLoading) {
        btn.disabled = true;
        input.disabled = true;
        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        
        // Show skeleton loaders
        showSkeletonLoaders();
    } else {
        btn.disabled = false;
        input.disabled = false;
        btnText.classList.remove('hidden');
        spinner.classList.add('hidden');
    }
}

// Search
async function handleSearch() {
    const input = document.getElementById('search-input').value.trim();
    if (!input) {
        showToast('Please enter a search query or URL', 'error');
        return;
    }

    // Get search mode from global variable set in HTML
    const searchMode = window.SEARCH_MODE || 'name';

    setSearchLoading(true);

    try {
        if (searchMode === 'name') {
            await searchByName(input);
        } else if (searchMode === 'url') {
            await searchByUrl(input);
        } else if (searchMode === 'playlist') {
            await searchByPlaylist(input);
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setSearchLoading(false);
    }
}

async function searchByName(query) {
    const data = await apiCall('/api/search', 'POST', { query, limit: 60 });
    searchResults = data.results;
    currentPage = 1; // Reset to first page
    renderResults();
}

async function searchByUrl(url) {
    const data = await apiCall('/api/video-info', 'POST', { url });
    searchResults = [data];
    currentPage = 1; // Reset to first page
    renderResults();
}

async function searchByPlaylist(url) {
    const data = await apiCall('/api/playlist-info', 'POST', { url });
    searchResults = data.videos;
    currentPage = 1; // Reset to first page
    renderResults();
    showToast(`Found ${data.summary.total} videos (${data.summary.new} new)`, 'success');
}

// Render Results
function renderResults() {
    const grid = document.getElementById('results-grid');

    if (searchResults.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <svg width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                </svg>
                <h3>No Results Found</h3>
                <p>Try a different search term</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = '';

    // Calculate pagination
    const totalPages = Math.ceil(searchResults.length / ITEMS_PER_PAGE);
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, searchResults.length);
    const pageResults = searchResults.slice(startIndex, endIndex);

    // Render current page videos
    pageResults.forEach(video => {
        const card = createVideoCard(video);
        grid.appendChild(card);
    });

    // Add pagination controls if needed
    if (totalPages > 1) {
        const paginationDiv = document.createElement('div');
        paginationDiv.className = 'pagination-controls';
        paginationDiv.innerHTML = `
            <button onclick="changePage(-1)" ${currentPage === 1 ? 'disabled' : ''}>
                ← Previous
            </button>
            <span class="page-info">
                Page ${currentPage} of ${totalPages}
                (Showing ${startIndex + 1}-${endIndex} of ${searchResults.length})
            </span>
            <button onclick="changePage(1)" ${currentPage === totalPages ? 'disabled' : ''}>
                Next →
            </button>
        `;
        grid.appendChild(paginationDiv);
    }
}

// Change page
function changePage(direction) {
    const totalPages = Math.ceil(searchResults.length / ITEMS_PER_PAGE);
    currentPage += direction;
    currentPage = Math.max(1, Math.min(currentPage, totalPages));
    renderResults();

    // Scroll to top of results
    document.getElementById('results-grid').scrollIntoView({ behavior: 'smooth' });
}

// Render Queue
function renderQueue() {
    const content = document.getElementById('queueContent');

    if (queue.length === 0) {
        content.innerHTML = `
            <div class="empty-state-small">
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M3 9h18v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9Z"></path>
                    <path d="m3 9 2.45-4.9A2 2 0 0 1 7.24 3h9.52a2 2 0 0 1 1.8 1.1L21 9"></path>
                    <path d="M12 3v6"></path>
                </svg>
                <p>Queue is empty</p>
            </div>
        `;
        return;
    }

    content.innerHTML = '';

    queue.forEach(video => {
        const item = createQueueItem(video);
        content.appendChild(item);
    });
    
    updateQueueUI();
}

// Create Video Card
function createVideoCard(video) {
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

    if (video.thumbnail) {
        thumbnail.src = video.thumbnail;
        thumbnail.onerror = function() {
            this.style.display = 'none';
            thumbnailContainer.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        };
    }

    const durationBadge = document.createElement('div');
    durationBadge.className = 'duration-badge';
    durationBadge.textContent = video.duration;

    thumbnailContainer.appendChild(thumbnail);
    thumbnailContainer.appendChild(durationBadge);

    // YouTube preview button
    const youtubeBtn = document.createElement('a');
    youtubeBtn.className = 'youtube-preview-btn';
    youtubeBtn.href = video.url;
    youtubeBtn.target = '_blank';
    youtubeBtn.rel = 'noopener noreferrer';
    youtubeBtn.title = 'Preview on YouTube';
    youtubeBtn.innerHTML = '▶';
    youtubeBtn.onclick = (e) => {
        e.stopPropagation(); // Prevent card click when clicking preview
    };
    thumbnailContainer.appendChild(youtubeBtn);

    // Status badge
    if (video.status && video.status !== 'new') {
        const statusBadge = document.createElement('div');
        statusBadge.className = 'status-badge';
        statusBadge.textContent = video.status === 'downloaded' ? 'Downloaded' : 'Queued';
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

    // Add to queue button
    if (video.status === 'new') {
        const addBtn = document.createElement('button');
        addBtn.className = 'add-to-queue-btn';
        addBtn.textContent = 'Add to Queue';
        addBtn.onclick = (e) => {
            e.stopPropagation();
            addSingleToQueue(video);
        };
        info.appendChild(addBtn);
    }

    card.appendChild(thumbnailContainer);
    card.appendChild(info);

    return card;
}

// Create Queue Item
function createQueueItem(video) {
    const item = document.createElement('div');
    item.className = 'queue-item';
    item.dataset.videoId = video.video_id;

    const title = document.createElement('div');
    title.className = 'queue-item-title';
    title.textContent = video.title;

    const channel = document.createElement('div');
    channel.className = 'queue-item-channel';
    channel.textContent = video.channel;

    const actions = document.createElement('div');
    actions.className = 'queue-item-actions';

    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'btn-primary';
    downloadBtn.textContent = 'Download';
    downloadBtn.onclick = () => downloadSingle(video.video_id);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-secondary';
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = () => removeFromQueue(video.video_id);

    actions.appendChild(downloadBtn);
    actions.appendChild(removeBtn);

    item.appendChild(title);
    item.appendChild(channel);
    item.appendChild(actions);

    return item;
}

// Add single video to queue
async function addSingleToQueue(video) {
    try {
        await apiCall('/api/library/add', 'POST', video);
        showToast('Added to queue', 'success');
        await loadStatus();
        await loadQueue();
        renderResults(); // Re-render to update button states
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Download single item from queue
async function downloadSingle(videoId) {
    try {
        await apiCall('/api/download', 'POST', [videoId]);
        showToast('Download started', 'success');
        
        // Poll for updates
        const interval = setInterval(async () => {
            await loadStatus();
            await loadQueue();
            
            const stillInQueue = queue.some(v => v.video_id === videoId);
            if (!stillInQueue) {
                clearInterval(interval);
                showToast('Download complete!', 'success');
            }
        }, 2000);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Functions removed - using quick add buttons instead

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

// Settings - removed duplicate, using modal version above

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
