// Shared video-card builder (docs/13 Track A).
//
// search.js's search-result cards and history.js's download-history cards
// used to be two independent, near-duplicate DOM builders (docs/11 agent 3's
// top structural-risk finding). This is now the one place that builds a
// `.video-card`'s DOM/classes; both callers parameterize it for what
// actually differs between them:
//   - which extra class dims an inert card (search: 'downloaded'/'queued'
//     (docs/09 AUD-13); history: 'downloaded'/'failed')
//   - whether a duration badge is shown (search only)
//   - the status badge text/class (search: 'new' cards get no badge,
//     'queued' gets `.status-badge.queued` per docs/09 AUD-06; history
//     always shows one, 'failed' gets `.status-badge.failed` per docs/09
//     AUD-26)
//   - whether a `.video-date` line is shown (history only)
//   - the action button (search: "Add to Queue"; history: "Retry")
//
// Markup/classes are unchanged from the pre-refactor versions -- this is a
// dedup, not a redesign.
function createCard(item, options) {
    const card = document.createElement('div');
    const extraClass = options.cardClass(item);
    card.className = extraClass ? `video-card ${extraClass}` : 'video-card';
    card.dataset.videoId = item.video_id;

    // Thumbnail
    const thumbnailContainer = document.createElement('div');
    thumbnailContainer.className = 'thumbnail-container';

    const thumbnail = document.createElement('img');
    thumbnail.className = 'thumbnail';
    thumbnail.alt = item.title;
    thumbnail.loading = 'lazy';

    if (item.thumbnail) {
        thumbnail.src = item.thumbnail;
        thumbnail.onerror = function () {
            this.style.display = 'none';
            thumbnailContainer.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        };
    }
    thumbnailContainer.appendChild(thumbnail);

    if (options.showDuration) {
        const durationBadge = document.createElement('div');
        durationBadge.className = 'duration-badge';
        durationBadge.textContent = item.duration;
        thumbnailContainer.appendChild(durationBadge);
    }

    // YouTube preview button
    const youtubeBtn = document.createElement('a');
    youtubeBtn.className = 'youtube-preview-btn';
    youtubeBtn.href = item.url;
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
    const badge = options.badge(item);
    if (badge) {
        const statusBadge = document.createElement('div');
        statusBadge.className = badge.extraClass ? `status-badge ${badge.extraClass}` : 'status-badge';
        statusBadge.textContent = badge.text;
        thumbnailContainer.appendChild(statusBadge);
    }

    // Info
    const info = document.createElement('div');
    info.className = 'video-info';

    const title = document.createElement('div');
    title.className = 'video-title';
    title.textContent = item.title;
    title.title = item.title;

    const channel = document.createElement('div');
    channel.className = 'video-channel';
    channel.textContent = item.channel;

    info.appendChild(title);
    info.appendChild(channel);

    if (options.dateField) {
        const date = document.createElement('div');
        date.className = 'video-date';
        date.textContent = item[options.dateField];
        info.appendChild(date);
    }

    const actionBtn = options.actionButton(item);
    if (actionBtn) {
        info.appendChild(actionBtn);
    }

    card.appendChild(thumbnailContainer);
    card.appendChild(info);

    return card;
}
