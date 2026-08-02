// Initialize -- loaded last so it can reference everything above.
// (Theme init is handled by nav.js, shared across all pages.)
document.addEventListener('DOMContentLoaded', async () => {
    initView();
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
