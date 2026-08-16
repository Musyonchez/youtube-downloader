// View Management
function toggleView(view) {
    currentView = view;
    localStorage.setItem('view', view);

    const grid = document.getElementById('results-grid');
    const buttons = document.querySelectorAll('.view-btn');

    // Update grid class
    if (view === 'compact') {
        grid?.classList.add('compact');
    } else {
        grid?.classList.remove('compact');
    }

    // Update button states
    buttons.forEach(btn => {
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function initView() {
    const savedView = localStorage.getItem('view') || 'grid';
    currentView = savedView;

    // Apply saved view
    const grid = document.getElementById('results-grid');
    const buttons = document.querySelectorAll('.view-btn');

    if (savedView === 'compact') {
        grid?.classList.add('compact');
    }

    // Update button states
    buttons.forEach(btn => {
        if (btn.dataset.view === savedView) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Results Filter (All / Downloaded / Not Downloaded)
function setResultsFilter(filter) {
    resultsFilter = filter;
    localStorage.setItem('resultsFilter', filter);
    currentPage = 1; // Reset to first page when the filter changes
    updateFilterButtons();
    renderResults();
}

function initResultsFilter() {
    resultsFilter = localStorage.getItem('resultsFilter') || 'all';
    updateFilterButtons();
}

function updateFilterButtons() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === resultsFilter);
    });
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
let settingsTriggerEl = null; // element to restore focus to when the modal closes

function toggleSettings() {
    const modal = document.getElementById('settings-modal');
    if (!modal) {
        console.error('Settings modal not found');
        return;
    }

    const opening = modal.classList.contains('hidden');
    modal.classList.toggle('hidden');

    if (opening) {
        settingsTriggerEl = document.activeElement;
        modal.querySelector('#audio-quality')?.focus();
    } else if (settingsTriggerEl) {
        settingsTriggerEl.focus();
        settingsTriggerEl = null;
    }
}

// Trap Tab/Shift+Tab inside the settings modal while it's open, so keyboard
// users can't tab out into the (visually blocked) page behind it.
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const modal = document.getElementById('settings-modal');
    if (!modal || modal.classList.contains('hidden')) return;

    const focusable = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
    }
});

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('settings-modal');
    if (e.target === modal?.querySelector('.modal-overlay')) {
        toggleSettings();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // ESC key to close modals and panels
    if (e.key === 'Escape' || e.key === 'Esc') {
        const settingsModal = document.getElementById('settings-modal');
        const mobileMenu = document.getElementById('mobileMenu');
        const queuePanel = document.getElementById('queuePanel');

        // Close settings modal if open
        if (settingsModal && !settingsModal.classList.contains('hidden')) {
            toggleSettings();
            return;
        }

        // Close mobile menu if open
        if (mobileMenu && mobileMenu.classList.contains('active')) {
            toggleMobileMenu();
            return;
        }

        // Close queue panel if open on mobile (width <= 968px)
        if (queuePanel && window.innerWidth <= 968 && !queuePanel.classList.contains('collapsed')) {
            toggleQueue();
            return;
        }
    }
});

// Toast Notifications -- showToast() now lives in cards.js (docs/16,
// 16-19), shared with history.js instead of being defined here too.

// Enter key for search
function handleSearchEnter(event) {
    if (event.key === 'Enter') {
        handleSearch();
    }
}
