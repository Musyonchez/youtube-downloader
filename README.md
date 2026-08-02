# YouTube MP3 Downloader (Web App)

A modern, professional SaaS-quality web application for downloading YouTube videos as high-quality MP3 files. Beautiful UI, real-time progress tracking, and accessible from any device on your network!

## Features

### 🎨 Modern UI/UX

- **Professional Landing Page**: SaaS-quality design with gradients and smooth animations
- **Light/Dark Theme Toggle**: Seamless theme switching with localStorage persistence
- **Split-Screen Layout**: 70% search results, 30% collapsible queue panel
- **Grid & Compact Views**: Toggle between card grid or compact list view
- **Skeleton Loaders**: Beautiful shimmer effects while searching
- **Responsive Design**: Perfect on desktop, tablet, and mobile

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
- **Clean Filenames**: "Artist - Title.mp3" format
- **Download History**: Track all 655+ downloads in `downloads.db` (SQLite)

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
   pip install -r requirements.txt

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
   ```

## Usage

### Quick Start

```bash
# Using the startup script (recommended)
./run.sh

# Or manually
source venv/bin/activate
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
   - Add individual videos or entire playlist

3. **URL** (`/app/url`):
   - Paste single video URL
   - Preview video info
   - Add to queue

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
│   ├── main.py               # FastAPI app instance, page routes, /ws
│   ├── ws_manager.py         # WebSocket connection manager
│   ├── utils.py              # Pure helpers (filenames, durations, URL parsing)
│   ├── api/
│   │   └── routes.py         # REST API endpoints
│   ├── services/
│   │   ├── search.py         # YouTube search with yt-dlp
│   │   └── downloader.py     # Download logic & progress tracking
│   └── storage/
│       ├── db.py             # SQLite wrapper (library queue & history)
│       └── storage.py        # Storage facade (config.json + db.py)
├── data/                     # Runtime data (config + library/history db)
│   ├── config.json           # User settings (quality, directory)
│   └── downloads.db          # Download queue + history (SQLite)
├── static/
│   ├── css/
│   │   ├── landing.css      # Landing page styles
│   │   └── app.css          # App split-screen layout
│   └── js/
│       ├── landing.js       # Landing page interactions
│       └── (app logic, split into state.js, api.js, ui.js,
│            search.js, queue.js, websocket.js, main.js)
├── templates/
│   ├── index.html           # Landing page
│   └── app.html             # Main app (3 search modes)
├── scripts/                 # One-off personal utility scripts
│   ├── download_temp.py
│   └── rename_bible.py
├── tests/                   # pytest suite
├── run.sh                   # Startup script
├── Makefile                 # Development commands
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Dev tools (mypy, ruff, flake8, pytest)
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
- `POST /api/library/add-multiple` - Add multiple videos
- `DELETE /api/library/{video_id}` - Remove from queue
- `DELETE /api/library` - Clear queue
- `POST /api/download` - Start downloading
- `GET /api/config` - Get settings
- `POST /api/config` - Update settings

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
✅ **Modern UI**: SaaS-quality design with smooth animations  
✅ **Real-time updates**: See download progress live  
✅ **No installation**: Works in any browser  
✅ **Remote control**: Queue from bed, download on PC  
✅ **Responsive**: Perfect layout on any screen size  
✅ **Theme support**: Light/dark mode with one click  
✅ **View options**: Grid or compact list view

## Troubleshooting

**Server won't start**

- Make sure venv is activated: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

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

- **JSON Files**: Git-friendly, human-readable
- **No Database**: Simple file-based storage
- **Download History**: Track 655+ songs efficiently

### Features

- **WebSockets**: Real-time progress updates
- **Page Visibility API**: Smart polling when tab is active
- **Skeleton Loaders**: Shimmer effects during loading
- **Toast Notifications**: Non-intrusive feedback

## License

Free to use for personal projects.

## Screenshots

### Landing Page

- Modern gradient hero section
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

### v2.0.0 (December 2025)

- ✨ Complete UI redesign with SaaS-quality landing page
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

**655 songs downloaded and counting!** 🎵
