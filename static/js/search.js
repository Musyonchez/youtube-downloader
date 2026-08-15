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

// Apply the current results filter (All / Downloaded / Not Downloaded).
// Persisted to localStorage by setResultsFilter() in ui.js; defaults to 'all'.
const FILTER_LABELS = { all: 'All', downloaded: 'Downloaded', 'not-downloaded': 'Not Downloaded' };

function getFilteredResults() {
    if (resultsFilter === 'downloaded') {
        return searchResults.filter(video => video.status === 'downloaded');
    }
    if (resultsFilter === 'not-downloaded') {
        return searchResults.filter(video => video.status !== 'downloaded');
    }
    return searchResults;
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

    const filteredResults = getFilteredResults();

    if (filteredResults.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <svg width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                </svg>
                <h3>No Matches</h3>
                <p>No videos match the "${FILTER_LABELS[resultsFilter]}" filter</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = '';

    // Calculate pagination
    const totalPages = Math.ceil(filteredResults.length / ITEMS_PER_PAGE);
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, filteredResults.length);
    const pageResults = filteredResults.slice(startIndex, endIndex);

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
                (Showing ${startIndex + 1}-${endIndex} of ${filteredResults.length})
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
    const totalPages = Math.ceil(getFilteredResults().length / ITEMS_PER_PAGE);
    currentPage += direction;
    currentPage = Math.max(1, Math.min(currentPage, totalPages));
    renderResults();

    // Scroll to top of results
    document.getElementById('results-grid').scrollIntoView({ behavior: 'smooth' });
}

// Create Video Card
function createVideoCard(video) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.dataset.videoId = video.video_id;

    if (video.status === 'downloaded') {
        card.classList.add('downloaded');
    } else if (video.status === 'queued') {
        // Queued cards have no click target (no Add button, nothing else
        // handles a card click) -- mark them inert the same way downloaded
        // cards are, instead of leaving a hover/pointer affordance that leads
        // nowhere.
        card.classList.add('queued');
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
    youtubeBtn.setAttribute('aria-label', 'Preview on YouTube');
    youtubeBtn.innerHTML = '▶';
    youtubeBtn.onclick = (e) => {
        e.stopPropagation(); // Prevent card click when clicking preview
    };
    thumbnailContainer.appendChild(youtubeBtn);

    // Status badge
    if (video.status && video.status !== 'new') {
        const statusBadge = document.createElement('div');
        statusBadge.className = video.status === 'downloaded' ? 'status-badge' : 'status-badge queued';
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
