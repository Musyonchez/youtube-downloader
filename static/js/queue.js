// Render Queue
// Tracks the inputs of the last render so an unchanged poll tick (queue.js's
// downloadSingle/downloadQueue poll every 1s while a download runs) can skip
// rebuilding the DOM entirely, rather than tearing down and recreating every
// queue item every second regardless of whether anything actually changed.
// As a side benefit, it also stops the poll from clobbering the percent text
// that websocket.js's updateQueueItemProgress() writes into those same
// nodes between polls.
let _lastQueueRenderKey = null;

function renderQueue() {
    const content = document.getElementById('queueContent');

    // Check if element exists
    if (!content) {
        console.warn('Queue content element not found');
        return;
    }

    const renderKey = JSON.stringify({ ids: queue.map(v => v.video_id), downloading: currentlyDownloading });
    if (renderKey === _lastQueueRenderKey) {
        return;
    }
    _lastQueueRenderKey = renderKey;

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
        updateQueueUI();
        return;
    }

    content.innerHTML = '';

    queue.forEach(video => {
        const item = createQueueItem(video);
        content.appendChild(item);
    });

    updateQueueUI();
}

// Create Queue Item
function createQueueItem(video) {
    const item = document.createElement('div');
    item.className = 'queue-item';
    item.dataset.videoId = video.video_id;

    // Check if this item is currently downloading
    const isCurrentlyDownloading = currentlyDownloading === video.video_id;
    if (isCurrentlyDownloading) {
        item.classList.add('downloading');
    }

    const title = document.createElement('div');
    title.className = 'queue-item-title';
    title.textContent = video.title;

    const channel = document.createElement('div');
    channel.className = 'queue-item-channel';
    channel.textContent = video.channel;

    // Add status indicator
    const status = document.createElement('div');
    status.className = isCurrentlyDownloading ? 'queue-item-status downloading' : 'queue-item-status pending';
    status.innerHTML = `
        <span class="status-icon"></span>
        <span class="status-text">${isCurrentlyDownloading ? 'Downloading' : 'Pending'}</span>
    `;

    const actions = document.createElement('div');
    actions.className = 'queue-item-actions';

    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'btn-primary';
    downloadBtn.textContent = 'Download';
    downloadBtn.onclick = () => downloadSingle(video.video_id);
    downloadBtn.disabled = isDownloading; // Disable if any download is in progress

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-secondary';
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = () => removeFromQueue(video.video_id);
    removeBtn.disabled = isDownloading; // Disable if any download is in progress

    actions.appendChild(downloadBtn);
    actions.appendChild(removeBtn);

    item.appendChild(title);
    item.appendChild(channel);
    item.appendChild(status);
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

        // Poll for updates every second
        const interval = setInterval(async () => {
            await loadStatus();
            await loadQueue(); // This calls renderQueue() internally

            const stillInQueue = queue.some(v => v.video_id === videoId);
            if (!stillInQueue) {
                clearInterval(interval);
                // Trust the actual outcome (from the WS download_complete
                // message) rather than assuming success just because the
                // item left the queue -- a failed download leaves the queue
                // too. The failure toast is already shown by websocket.js;
                // only announce success here, and only when we know it.
                const succeeded = downloadOutcomes[videoId];
                delete downloadOutcomes[videoId];
                if (succeeded !== false) {
                    showToast('Download complete!', 'success');
                }
            }
        }, 1000); // Poll every second
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
    // Prevent multiple simultaneous downloads
    if (isDownloading) {
        showToast('Download already in progress', 'error');
        return;
    }

    try {
        isDownloading = true;
        const downloadBtn = document.getElementById('download-btn');
        if (downloadBtn) {
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Downloading...';
        }

        const data = await apiCall('/api/download', 'POST');
        showToast(data.message, 'success');

        // Set first item as currently downloading and re-render
        if (queue.length > 0) {
            currentlyDownloading = queue[0].video_id;
            console.log('Starting download with:', queue[0].title);
            renderQueue(); // Show initial downloading state
        }

        // Poll for updates every second so the queue count/list stay
        // current. Which item is "currently downloading" is no longer
        // inferred here (docs/16, 16-23) -- websocket.js's progress
        // handler sets currentlyDownloading directly from the server's
        // own messages, which can't desync the way a queue-length-delta
        // guess could if a video was added mid-batch.
        const interval = setInterval(async () => {
            await loadStatus();
            await loadQueue(); // This calls renderQueue() internally

            if (queue.length === 0) {
                // Queue is empty - stop everything
                console.log('Queue empty - stopping download');
                clearInterval(interval);
                isDownloading = false;
                currentlyDownloading = null;
                showToast('All downloads complete!', 'success');

                if (downloadBtn) {
                    downloadBtn.textContent = 'Download All';
                    downloadBtn.disabled = true;
                }

                const clearBtn = document.getElementById('clear-btn');
                if (clearBtn) clearBtn.disabled = true;

                // Force re-render to clear any downloading states
                renderQueue();
            }
        }, 1000); // Poll every second for smoother updates
    } catch (error) {
        isDownloading = false;
        currentlyDownloading = null;
        const downloadBtn = document.getElementById('download-btn');
        if (downloadBtn) {
            downloadBtn.textContent = 'Download All';
            downloadBtn.disabled = queue.length === 0;
        }
        renderQueue(); // Reset UI
        showToast(error.message, 'error');
    }
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
