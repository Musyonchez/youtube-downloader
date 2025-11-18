# YouTube MP3 Downloader (Web App)

A modern web-based YouTube downloader with thumbnail preview and intuitive UI. Access from any device on your network - PC, phone, or tablet!

## Features

- **🌐 Web Interface**: Access from any device with a browser
- **📱 Mobile Friendly**: Browse and queue songs from your phone while downloads happen on PC
- **🖼️ Thumbnail Preview**: See video thumbnails before adding to queue
- **3 Search Modes**:
  - Search by name with visual results
  - Add by single video URL
  - Add entire playlists at once
- **Smart Queue Management**:
  - Visual grid of queued videos
  - Status indicators (New, Queued, Downloaded)
  - Duplicate detection using video IDs
- **High-Quality Audio**:
  - Default 320kbps MP3 (configurable)
  - Automatic metadata tagging (artist, title, album)
  - Clean filename format: "Artist - Title.mp3"
- **Real-Time Updates**:
  - Download progress tracking
  - Live status updates
  - Toast notifications

## Installation

1. **Navigate to project**:
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
   pip install -r requirements.txt
   ```

4. **Install FFmpeg** (required for audio conversion):
   ```bash
   sudo pacman -S ffmpeg  # Arch Linux
   ```

## Usage

### Quick Start

```bash
# Using the startup script (recommended)
./run.sh

# Or manually
source venv/bin/activate
python app.py
```

The server will start and display:
```
🖥️  Local:   http://localhost:8000
📱 Network: http://192.168.1.x:8000
```

### Access from Different Devices

- **On the same PC**: Open `http://localhost:8000`
- **From phone/tablet**: Open `http://<your-pc-ip>:8000`
- **Find your PC's IP**: Run `hostname -I` on Linux

### Using the Web Interface

1. **Search for Videos**:
   - Enter search query or paste URL
   - Select search type (Name, URL, or Playlist)
   - Click Search

2. **Browse Results**:
   - See thumbnails and video info
   - Videos show status badges:
     - No badge = New (can add to queue)
     - ✓ = Already downloaded
     - 📥 = Already in queue

3. **Add to Queue**:
   - Click videos to select (they'll highlight in blue)
   - Click "Add Selected to Queue"

4. **Download**:
   - View your queue at the bottom
   - Click "Download All" to start
   - Progress updates in real-time

5. **Settings**:
   - Click ⚙️ Settings
   - Change audio quality (128-320kbps)
   - Change download directory

## Project Structure

```
youtube-downloader/
├── app.py                 # FastAPI server
├── api/
│   ├── __init__.py
│   └── routes.py         # API endpoints
├── static/
│   ├── css/
│   │   └── style.css     # Modern dark theme
│   └── js/
│       └── app.js        # Frontend logic
├── templates/
│   └── index.html        # Main web page
├── utils.py              # Storage & helpers
├── search.py             # YouTube search
├── downloader.py         # Download logic
├── run.sh                # Startup script
├── requirements.txt      # Python dependencies
├── config.json           # User settings
├── library.json          # Download queue
├── downloaded.json       # Download history
└── downloads/            # MP3 files
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

Default settings in `config.json`:
```json
{
  "audio_quality": "320",
  "format": "mp3",
  "download_dir": "./downloads",
  "last_updated": "2025-11-19"
}
```

Settings can be changed through the web UI or by editing the file.

## Use Cases

### Scenario 1: Browsing from Phone
1. Lying in bed with your phone
2. Open the web app on phone
3. Search and add songs to queue
4. Downloads happen automatically on PC
5. Next day, songs are ready in your music folder

### Scenario 2: Building a Playlist
1. Find a YouTube playlist you like
2. Paste the playlist URL
3. See all videos with thumbnails
4. Select which ones to download
5. Click "Add Selected to Queue"
6. Download all at once

### Scenario 3: Quick Single Download
1. Find a song on YouTube (on any device)
2. Copy the URL
3. Paste in web app
4. Add to queue and download
5. Done!

## Advantages Over Desktop GUI

✅ Access from **any device** (phone, tablet, laptop)
✅ Browse while **away from PC**
✅ **Modern web UI** looks great
✅ **Thumbnails** work perfectly
✅ No need to sit at your PC
✅ Can manage downloads **remotely**

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
ExecStart=/home/musyonchez/Code/youtube-downloader/venv/bin/python app.py
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

- **Backend**: FastAPI, yt-dlp, mutagen
- **Frontend**: Vanilla JavaScript, modern CSS
- **Storage**: JSON files (git-friendly)
- **Real-time**: WebSockets

## License

Free to use for personal projects.

---

Made with ❤️ for music lovers who want to build their own library
