// Download History page (docs/09, AUD-26). Self-contained -- this page
// doesn't share state.js/queue.js/search.js/ui.js with the app page, since
// most of that module set is queue/search-specific and assumes DOM
// elements (queue panel, settings modal, results filter for *search*
// results) this page doesn't have. Only api.js (apiCall) and nav.js
// (shared navbar/theme) are reused.

let historyItems = [];
let historyFilter = 'all'; // 'all' | 'success' | 'failed'
let historySearch = '';
let historyPage = 1;
const HISTORY_ITEMS_PER_PAGE = 24;

async function loadHistory() {
    const grid = document.getElementById('results-grid');
    try {
        const data = await apiCall('/api/downloaded');
        // The API returns ascending by downloaded_at; newest-first reads
        // better for a history view.
        historyItems = [...data.downloaded].reverse();
        document.getElementById('history-total').textContent = historyItems.length;
        document.getElementById('history-failed').textContent = historyItems.filter(i => !i.success).length;
        renderHistory();
    } catch (error) {
        grid.innerHTML = `
            <div class="empty-state">
                <h3>Couldn't load history</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function setHistoryFilter(filter) {
    historyFilter = filter;
    historyPage = 1;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filter);
    });
    renderHistory();
}

function getFilteredHistory() {
    let items = historyItems;
    if (historyFilter === 'success') items = items.filter(i => i.success);
    if (historyFilter === 'failed') items = items.filter(i => !i.success);
    if (historySearch) {
        const q = historySearch.toLowerCase();
        items = items.filter(i => i.title.toLowerCase().includes(q) || i.channel.toLowerCase().includes(q));
    }
    return items;
}

function renderHistory() {
    const grid = document.getElementById('results-grid');

    if (historyItems.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <h3>No downloads yet</h3>
                <p>Downloaded (and failed) videos will show up here.</p>
            </div>
        `;
        return;
    }

    const filtered = getFilteredHistory();

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <h3>No matches</h3>
                <p>Nothing matches the current filter/search.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = '';

    const totalPages = Math.ceil(filtered.length / HISTORY_ITEMS_PER_PAGE);
    historyPage = Math.min(historyPage, totalPages) || 1;
    const start = (historyPage - 1) * HISTORY_ITEMS_PER_PAGE;
    const end = Math.min(start + HISTORY_ITEMS_PER_PAGE, filtered.length);

    filtered.slice(start, end).forEach(item => grid.appendChild(createHistoryCard(item)));

    if (totalPages > 1) {
        const pagination = document.createElement('div');
        pagination.className = 'pagination-controls';
        pagination.innerHTML = `
            <button onclick="changeHistoryPage(-1)" ${historyPage === 1 ? 'disabled' : ''}>
                ← Previous
            </button>
            <span class="page-info">
                Page ${historyPage} of ${totalPages}
                (Showing ${start + 1}-${end} of ${filtered.length})
            </span>
            <button onclick="changeHistoryPage(1)" ${historyPage === totalPages ? 'disabled' : ''}>
                Next →
            </button>
        `;
        grid.appendChild(pagination);
    }
}

function changeHistoryPage(direction) {
    const totalPages = Math.ceil(getFilteredHistory().length / HISTORY_ITEMS_PER_PAGE);
    historyPage = Math.max(1, Math.min(historyPage + direction, totalPages));
    renderHistory();
    document.getElementById('results-grid').scrollIntoView({ behavior: 'smooth' });
}

// Thin wrapper around cards.js's shared builder (docs/13 Track A),
// parameterized for history items specifically.
function createHistoryCard(item) {
    return createCard(item, {
        cardClass: (i) => (i.success ? 'downloaded' : 'failed'),
        showDuration: false,
        // docs/09 AUD-26: distinct badge class for 'failed' vs 'downloaded'.
        // Unlike search results, history cards always show a badge.
        badge: (i) => (i.success
            ? { text: 'Downloaded', extraClass: null }
            : { text: 'Failed', extraClass: 'failed' }),
        dateField: 'downloaded_at',
        actionButton: (i) => {
            if (i.success) return null;
            // AUD-02 made failures durable specifically so they could be
            // retried -- this closes that loop instead of leaving the
            // failure record purely informational.
            const retryBtn = document.createElement('button');
            retryBtn.className = 'add-to-queue-btn';
            retryBtn.textContent = 'Retry';
            retryBtn.onclick = (e) => {
                e.stopPropagation();
                retryDownload(i, retryBtn);
            };
            return retryBtn;
        },
    });
}

async function retryDownload(item, btn) {
    btn.disabled = true;
    btn.textContent = 'Adding...';
    try {
        await apiCall('/api/library/add', 'POST', {
            video_id: item.video_id,
            title: item.title,
            channel: item.channel,
            duration: item.duration,
            url: item.url,
            thumbnail: item.thumbnail,
        });
        showToast('Added to queue -- open Search to download it', 'success');
        btn.textContent = 'Queued';
    } catch (error) {
        showToast(error.message, 'error');
        btn.disabled = false;
        btn.textContent = 'Retry';
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();

    let searchDebounce;
    document.getElementById('history-search').addEventListener('input', (e) => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => {
            historySearch = e.target.value.trim();
            historyPage = 1;
            renderHistory();
        }, 200);
    });
});
