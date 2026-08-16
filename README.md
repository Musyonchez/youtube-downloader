# YouTube MP3 Downloader (Web App)

[![CI](https://github.com/Musyonchez/youtube-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/Musyonchez/youtube-downloader/actions/workflows/ci.yml)

A self-hosted web app for turning YouTube videos into high-quality MP3s — search, queue, and download from your phone while the actual work happens on your own server. Real-time progress, a persistent library with full download history, and a warm, distinctive UI instead of another generic dashboard template.

## Features

### 🎨 UI/UX

- **A design that isn't a template**: a copper/teal "warm analog" palette (audio-equipment inspired), a distinctive heading typeface, and a real motion pass — not the default indigo-gradient look most AI-generated UIs ship with
- **Light/Dark Theme Toggle**: Seamless theme switching with localStorage persistence
- **Split-Screen Layout**: 70% search results, 30% collapsible queue panel
- **Grid & Compact Views**: Toggle between card grid or compact list view
- **Skeleton Loaders**: Shimmer effects while searching
- **Responsive Design**: Desktop, tablet, and mobile
- **Reduced-motion support**: respects your OS-level `prefers-reduced-motion` setting throughout

### 🔍 Three Search Modes

- **Search by Name**: Find videos with visual grid results and thumbnails
- **Single URL**: Paste a YouTube video URL for quick downloads
- **Playlist**: Add entire playlists at once with preview

### 📥 Smart Queue Management

- **Real-Time Progress**: Live download status with pulsing indicators
- **Quick Add Buttons**: One-click add from search results
- **Individual Downloads**: Download single items or entire queue
- **Status Tracking**: Visual indicators (Pending, Downloading, Downloaded)
- **Floating Queue Button**: Always accessible with badge counter
- **Duplicate Prevention**: Won't download the same video twice

### 🎵 High-Quality Audio

- **320kbps MP3** (configurable: 128/192/256/320 kbps)
- **Automatic Metadata**: Artist, title, and album tags
- **Collision-safe filenames**: "Artist - Title [video_id].mp3" — two videos with the same title never overwrite each other
- **Full Download History**: every attempt (success *and* failure) is recorded in SQLite and browsable on the `/history` page, with a one-click retry for failed downloads
- **Results filter**: toggle search results between All / Downloaded / Not Downloaded, persisted across sessions

### ⚡ User Experience

- **YouTube Preview**: Hover thumbnails to see play button, opens video in new tab
- **Pagination**: Navigate large search results easily
- **Keyboard Shortcuts**: Enter to search, ESC to close modals
- **Toast Notifications**: Non-intrusive status messages
- **Empty States**: Helpful SVG icons and messages

## Installation

1. **Clone or navigate to project**:

   ```bash
   cd ~/Code/youtube-downloader
   ```

2. **Create virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   # Production dependencies
   make install

   # Or manually
   pip install -r requirements.lock

   # Optional: Development tools (linting, type checking)
   make install-dev
   ```

4. **Install FFmpeg** (required for audio conversion):

   ```bash
   # Arch Linux
   sudo pacman -S ffmpeg

   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   winget install Gyan.FFmpeg
   ```

   Without FFmpeg, downloads fail with a clear "FFmpeg not found" error rather than silently leaving a non-MP3 file behind (the raw pre-conversion download) under a filename that looks like the expected MP3.

## Usage

### Quick Start

```bash
# Using the startup script (recommended) -- Linux/macOS/Git Bash
./run.sh

# Or manually
source venv/bin/activate
python -m app.main
```

On native Windows PowerShell (not Git Bash), use `run.ps1` instead:

```powershell
.\run.ps1

# Or manually
venv\Scripts\Activate.ps1
python -m app.main
```

The server will start and display:

```
🎵 YouTube MP3 Downloader
==========================
✅ Starting server...
🖥️  Local:   http://localhost:8000
📱 Network: http://10.1.9.38:8000
```

### Access from Different Devices

- **On the same PC**: Open `http://localhost:8000`
- **From phone/tablet**: Open `http://<your-pc-ip>:8000`
- **Find your PC's IP**: Run `hostname -I` on Linux

### Using the Web Interface

#### Landing Page

- Visit `http://localhost:8000` for the beautiful landing page
- Choose your search mode: **Name**, **Playlist**, or **URL**
- Toggle light/dark theme with the theme button

#### Search Modes

1. **Search by Name** (`/app/name`):
   - Enter keywords (e.g., "Ed Sheeran Perfect")
   - Browse visual grid with thumbnails
   - Toggle between Grid and Compact view
   - Click "Add to Queue" on any video

2. **Playlist** (`/app/playlist`):
   - Paste YouTube playlist URL
   - See all videos with metadata
   - Add videos to the queue individually

3. **URL** (`/app/url`):
   - Paste single video URL
   - Preview video info
   - Add to queue

#### History (`/history`)

- Every download attempt this app has ever recorded, success or failure
- Filter by All / Downloaded / Failed, or search by title/channel
- Failed downloads get a **Retry** button (re-adds to the queue)

#### Queue Management

- **View Queue**: Toggle panel with X button or floating shelf icon
- **Status Indicators**:
  - Gray dot = Pending
  - Purple pulsing dot = Currently downloading
  - Green badge = Already downloaded
- **Download Options**:
  - "Download All" - Process entire queue sequentially
  - Individual download buttons per item
  - Real-time progress updates

#### Settings

- Click ⚙️ icon in navbar
- **Audio Quality**: 128/192/256/320 kbps
- **Download Directory**: Custom path
- Settings persist across sessions

## Project Structure

```
youtube-downloader/
├── app/                      # Python package -- run as `python -m app.main`
│   ├── main.py               # FastAPI app instance, page routes (incl. /login, /register), /ws
│   ├── session_auth.py       # Session-cookie auth gate (see docs/15)
│   ├── passwords.py           # PBKDF2 password hashing
│   ├── ws_manager.py         # WebSocket connection manager
│   ├── utils.py              # Pure helpers (filenames, durations, URL parsing)
│   ├── api/
│   │   └── routes.py         # REST API endpoints
│   ├── services/
│   │   ├── search.py         # YouTube search with yt-dlp
│   │   ├── downloader.py     # Download logic & progress tracking
│   │   └── download_orchestrator.py  # Batch-download queue logic (used by api/routes.py)
│   └── storage/
│       ├── db.py             # SQLite wrapper (library queue & history)
│       └── storage.py        # Storage facade (config.json + db.py)
├── data/                     # Runtime data (config + library/history db)
│   ├── config.json           # User settings (quality, directory)
│   └── downloads.db          # Download queue + history (SQLite)
├── static/
│   ├── css/
│   │   ├── variables.css    # Shared design tokens (palette, fonts, motion) -- see docs/12
│   │   ├── landing.css      # Landing page styles
│   │   ├── app.css          # App split-screen layout
│   │   └── history.css      # Download history page
│   └── js/
│       ├── cards.js         # Shared video-card builder (search + history pages) -- see docs/13
│       ├── landing.js       # Landing page interactions
│       ├── history.js       # Download history page (self-contained)
│       └── (app logic, split into state.js, api.js, ui.js,
│            search.js, queue.js, websocket.js, main.js)
├── templates/
│   ├── index.html           # Landing page
│   ├── app.html             # Main app (3 search modes)
│   └── history.html         # Download history page
├── scripts/                 # One-off personal utility scripts
│   ├── download_temp.py
│   └── rename_bible.py
├── extension/                # Chrome (MV3) extension -- "Send to MP3 Queue"
│   │                          # button on YouTube; sibling dir, never part of
│   │                          # the server's Docker image. See extension/README.md.
│   ├── manifest.json
│   ├── background.js         # Service worker -- the only place that calls the API
│   ├── content.js/.css       # Floating button injected on youtube.com
│   └── popup/                # Toolbar icon popup (login status + web app link)
├── tests/                   # pytest suite (+ tests/e2e/ for Playwright browser tests)
├── docs/                    # Audits, redesign history, deployment runbook -- see docs/README.md
├── run.sh                   # Startup script (Linux/macOS/Git Bash)
├── run.ps1                  # Startup script (native Windows PowerShell)
├── Makefile                 # Development commands
├── requirements.txt         # Production dependencies (loose >= bounds)
├── requirements.lock        # Same, pinned to exact versions -- what Dockerfile/CI actually install (see its header)
├── requirements-dev.txt     # Dev tools (mypy, ruff, flake8, pytest)
├── fly.toml                 # Fly.io deploy config -- see docs/14-deployment.md
├── CONTRIBUTING.md           # Branch/PR workflow (master is branch-protected)
└── downloads/                # MP3 output directory
```

## API Endpoints

The web app exposes a REST API:

- `GET /api/status` - Get queue and download counts
- `POST /api/search` - Search YouTube
- `POST /api/video-info` - Get video info from URL
- `POST /api/playlist-info` - Get playlist info
- `GET /api/library` - Get download queue
- `POST /api/library/add` - Add video to queue
- `DELETE /api/library/{video_id}` - Remove from queue
- `DELETE /api/library` - Clear queue
- `POST /api/download` - Start downloading (409 if a download is already running)
- `GET /api/downloaded?limit=&offset=` - Get a page of download history (success and failed attempts, newest first) plus the total count -- see the `/history` page
- `GET /api/config` - Get settings
- `POST /api/config` - Update settings

Every route above requires a logged-in session (docs/15) -- see `POST /login`,
`GET /login`, `POST /register`, `GET /register`, and `POST /logout`, served
from `app/main.py` rather than this REST API (they render HTML pages, not
JSON). Registration is only open while zero accounts exist.

## Configuration

Default settings in `data/config.json`:

```json
{
  "audio_quality": "320",
  "format": "mp3",
  "download_dir": "./downloads",
  "last_updated": "2025-11-19"
}
```

Settings can be changed through the web UI or by editing the file.

## Development

### Available Commands

```bash
# Run all code quality checks (syntax, types, lint, tests)
make check

# Format code with ruff
make format

# Run type checking
make type-check

# Run linting
make lint

# Run the test suite
make test

# Run browser smoke tests (Playwright, mocked search -- one-time setup:
# cd tests/e2e && npm install && npx playwright install chromium)
make e2e

# Clean cache files
make clean

# Run application
make run
```

All commands automatically use the virtual environment.

### Code Quality

- **Syntax Check**: ✅ All files compile without errors
- **Type Checking**: Uses mypy with type hints
- **Linting**: Ruff + Flake8 for code quality
- **Formatting**: Automatic code formatting with ruff
- **Tests**: pytest suite covering the pure-logic helpers, SQLite storage layer, and API request validation
- **Browser tests**: Playwright smoke tests (`tests/e2e/`) drive the real app in headless Chromium against a mocked search backend, catching frontend/backend contract bugs pytest can't see (see `docs/05-browser-verification.md`)
- **CI**: GitHub Actions runs the full check suite plus the Playwright smoke tests on every push/PR to `master` (see `.github/workflows/ci.yml`)

### Running with Docker

```bash
docker compose up --build
```

This builds the app with FFmpeg included and mounts `downloads/` and `data/` (containing `config.json` and `downloads.db`) from the host so your library and settings persist across container restarts. The app is then available at `http://localhost:8000` same as running it directly.

### Deploying to Fly.io

This app was originally built assuming LAN-only access with no login; it
now has real session-cookie auth instead (see [docs/15-auth-plan.md](docs/15-auth-plan.md)).
The account is single-user and first-come-first-served: the first person
to submit `/register` becomes the account, and registration closes
immediately afterward (server-enforced, not just hidden in the UI). Set
`SECRET_KEY` as a persistent Fly secret before deploying — it signs the
session cookie, and without it a fresh random key is generated on every
process start, silently logging everyone out on each restart/redeploy.
See [docs/14-deployment.md](docs/14-deployment.md) for the full runbook,
including persistent volumes and the CD pipeline. Local/LAN use still
works the same way (register the first account, then log in) — cookies
just aren't marked `Secure` outside a real deploy (detected via Fly's own
`FLY_APP_NAME` env var, or an explicit `ENVIRONMENT=production`), since a
`Secure` cookie is never sent back over plain HTTP.

### Contributing

`master` is branch-protected — see [CONTRIBUTING.md](CONTRIBUTING.md) for
the branch → PR → squash-merge workflow.

## Use Cases

### Scenario 1: Browsing from Phone

1. Lying in bed scrolling through music
2. Open web app on phone (`http://<pc-ip>:8000`)
3. Search and add songs to queue with one tap
4. Downloads happen automatically on PC
5. Wake up with music ready in your library!

### Scenario 2: Building a Playlist

1. Find a YouTube playlist you like
2. Switch to Playlist mode
3. Paste URL - see all 50+ videos with thumbnails
4. Toggle to compact view for better overview
5. Quick-add your favorites
6. Download entire queue with one click

### Scenario 3: Quick Single Download

1. Hear a song you like on YouTube
2. Copy URL on any device
3. Open web app, paste in URL mode
4. Add to queue and download
5. High-quality MP3 ready in seconds!

### Scenario 4: Theme Preference

1. Prefer light mode? Toggle theme button
2. Preference saves automatically
3. Works across all pages (landing + app)
4. Synced via localStorage

## Advantages Over Desktop Apps

✅ **Access anywhere**: Phone, tablet, laptop - same WiFi, same app  
✅ **Distinctive UI**: a real design pass, not the generic default  
✅ **Real-time updates**: See download progress live  
✅ **No installation**: Works in any browser  
✅ **Remote control**: Queue from bed, download on PC  
✅ **Responsive**: Perfect layout on any screen size  
✅ **Theme support**: Light/dark mode with one click  
✅ **View options**: Grid or compact list view

## Troubleshooting

**Server won't start**

- Make sure venv is activated: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.lock`

**Can't access from phone**

- Check your PC's firewall
- Make sure phone is on same WiFi network
- Use correct IP address (run `hostname -I`)

**Thumbnails not loading**

- Check internet connection
- YouTube may be throttling requests
- Try again in a few minutes

**Downloads failing**

- Make sure FFmpeg is installed: `sudo pacman -S ffmpeg`
- Check download directory permissions
- Ensure enough disk space

## Auto-Start on Boot (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/youtube-downloader.service
```

```ini
[Unit]
Description=YouTube MP3 Downloader Web App
After=network.target

[Service]
Type=simple
User=musyonchez
WorkingDirectory=/home/musyonchez/Code/youtube-downloader
ExecStart=/home/musyonchez/Code/youtube-downloader/venv/bin/python -m app.main
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable youtube-downloader
sudo systemctl start youtube-downloader
```

## Legal Notice

This tool is for personal use only. Downloading copyrighted content without permission may be illegal in your jurisdiction. Use responsibly.

## Tech Stack

### Backend

- **FastAPI**: Modern Python web framework with async support
- **yt-dlp**: YouTube downloading and metadata extraction
- **mutagen**: MP3 tagging (artist, title, album)
- **rich**: Beautiful terminal progress bars

### Frontend

- **Vanilla JavaScript**: No frameworks, pure ES6+
- **Modern CSS**: CSS Grid, Flexbox, custom properties
- **Responsive Design**: Mobile-first approach
- **localStorage**: Theme and view preference persistence

### Storage

- **SQLite** (`data/downloads.db`): the download queue and full history — indexed lookups instead of scanning a flat file, handles a large, growing library without slowing down
- **JSON** (`data/config.json`): user settings only (audio quality, download directory) — small, rarely written, no query needs, so a database would be pure overhead there

### Features

- **WebSockets**: Real-time progress updates
- **Page Visibility API**: Smart polling when tab is active
- **Skeleton Loaders**: Shimmer effects during loading
- **Toast Notifications**: Non-intrusive feedback

## License

Free to use for personal projects.

## Screenshots

### Landing Page

- Copper/teal hero with a realistic search-results preview and a waveform accent
- Three search mode options
- Light/dark theme toggle

### App Interface

- 70/30 split-screen layout
- Search results with thumbnails
- Collapsible queue panel
- Real-time download progress

### Mobile View

- Full-screen queue overlay
- Responsive grid layout
- Touch-friendly controls

---

## Changelog

### Unreleased

- 🔒 Post-auth audit fixes, all 26 findings (see `docs/16`): atomic
  first-account registration (closes a two-different-usernames race),
  per-username login rate limiting, a real `ENVIRONMENT`/`FLY_APP_NAME`-based
  signal for Secure cookies (instead of inferring it from whether
  `SECRET_KEY` was set), a server-side minimum password length, paginated
  download-history API/page, one shared `Storage` instance instead of two,
  URL-allowlist validation on `/api/library/add`, a batch-download loop
  that no longer aborts on one video's write failure, frontend auth-loss
  detection (401/`4401` redirect to `/login`), a pinned dependency
  lockfile (`requirements.lock`), an explicit `DATA_DIR` env var instead
  of an implicit relative-path/volume-mount coupling, a cached
  `registration_open()` check, a login-timing side-channel fix, a
  WS-driven (instead of queue-length-inferred) "currently downloading"
  indicator, plus a set of smaller UI/accessibility/contrast fixes (mobile
  navbar on the login/register pages, `aria-expanded` on the mobile menu
  button, auth-error and accent-as-text color contrast, a deduplicated
  `showToast`)

### v3.0.0

- ✨ Full audit pass: concurrency-safe downloads, durable/retryable failure
  records, batched status lookups, `/history` page, and a large accessibility
  pass (see `docs/09`)
- ✨ Complete visual redesign: warm copper/teal palette, distinctive
  typography, reduced-motion support, a real landing-page identity instead
  of a generic template (see `docs/10`–`13`)
- ✨ HTTP Basic Auth (opt-in via env vars) for deploying outside a trusted LAN
- ✨ Fly.io deployment support with persistent volumes and CD

### v2.0.0 (December 2025)

- ✨ Complete UI redesign with a split-screen landing page
- ✨ Split-screen layout (70% results, 30% queue)
- ✨ Light/dark theme toggle with persistence
- ✨ Grid/compact view toggle for search results
- ✨ Skeleton loading animations
- ✨ Real-time download progress indicators
- ✨ Quick-add buttons on video cards
- ✨ YouTube preview button on thumbnails
- ✨ Pagination for large result sets
- ✨ Floating queue button with badge counter
- 🔧 Improved mobile responsiveness
- 🔧 Better keyboard shortcuts (Enter, ESC)
- 🔧 Enhanced empty states with SVG icons

### v1.0.0 (Previous)

- Basic web interface
- Search and download functionality
- Queue management
- Settings panel

---

Made with ❤️ for music lovers who want to build their own library
