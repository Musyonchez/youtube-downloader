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
            // Drive the "downloading" highlight from the server's own
            // progress messages (docs/16, 16-23) instead of inferring it
            // from queue-length deltas between polls (queue.js's
            // downloadQueue loop used to do "queue got shorter -> assume
            // queue[0] is now downloading", which desyncs -- shows a
            // stuck or missing badge -- if a video is added to the
            // library mid-batch and shifts what queue[0] actually is).
            // Every progress message already carries the real video_id
            // that's actually downloading, so just trust it directly.
            if (data.video_id !== currentlyDownloading) {
                currentlyDownloading = data.video_id;
                renderQueue();
            }
        } else if (data.type === 'download_complete') {
            // Recorded so downloadSingle() (queue.js) can report the real
            // outcome instead of assuming success once the item leaves the queue.
            downloadOutcomes[data.video_id] = data.success;
            if (!data.success) {
                showToast('A download failed -- check the server logs', 'error');
            }
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = (event) => {
        // 4401 (app/session_auth.py's handshake-rejection code, docs/16,
        // 16-14) means this session isn't authenticated -- retrying that
        // handshake will only ever be rejected again, so a logged-out tab
        // must not keep reconnecting forever. Send the user to /login
        // instead, same as apiCall()'s 401 handling (api.js).
        if (event.code === 4401) {
            window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
            return;
        }
        // Otherwise: server restarted or connection dropped -- reconnect
        // after a delay.
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
