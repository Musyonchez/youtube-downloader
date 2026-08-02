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

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// Enter key for search
function handleSearchEnter(event) {
    if (event.key === 'Enter') {
        handleSearch();
    }
}
