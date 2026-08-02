// WebSocket -- live download progress, broadcast from downloader.py's yt-dlp
// progress hook via api/routes.py. The queue list itself is still refreshed
// via polling (loadQueue/loadStatus); this only fills in per-item percent.
function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'progress') {
            updateQueueItemProgress(data.video_id, data.percent);
        } else if (data.type === 'download_complete' && !data.success) {
            showToast('A download failed -- check the server logs', 'error');
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        // Server restarted or connection dropped -- reconnect after a delay.
        setTimeout(setupWebSocket, 3000);
    };
}

function updateQueueItemProgress(videoId, percent) {
    const item = document.querySelector(`.queue-item[data-video-id="${videoId}"]`);
    const statusText = item?.querySelector('.status-text');
    if (statusText) {
        statusText.textContent = percent >= 100 ? 'Finishing up...' : `Downloading ${percent}%`;
    }
}
