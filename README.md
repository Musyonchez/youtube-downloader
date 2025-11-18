# YouTube MP3 Downloader

A terminal-based YouTube downloader with an interactive TUI for downloading audio as MP3 files. Built as a personal music library manager and Spotify alternative.

## Features

- **3 Search Modes**:
  - Search by name (interactive search results)
  - Add by single video URL
  - Add by playlist URL (batch import)

- **Smart Library Management**:
  - Queue system for videos to download
  - Permanent download history (never re-download)
  - Status indicators (New, Queued, Downloaded)
  - Duplicate detection using video IDs

- **High-Quality Audio**:
  - Default 320kbps MP3 (configurable)
  - Automatic metadata tagging (artist, title, album)
  - Clean filename format: "Artist - Title.mp3"

- **Beautiful TUI**:
  - Interactive menus with questionary
  - Rich progress bars and formatted output
  - Easy navigation and management

## Installation

1. **Clone or navigate to the project**:
   ```bash
   cd youtube-downloader
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (required for audio conversion):

   **Linux (Arch)**:
   ```bash
   sudo pacman -S ffmpeg
   ```

   **Ubuntu/Debian**:
   ```bash
   sudo apt install ffmpeg
   ```

   **macOS**:
   ```bash
   brew install ffmpeg
   ```

## Usage

Run the application:
```bash
python main.py
```

### Main Menu Options

1. **🔍 Search by name**
   - Enter search query
   - Browse results with status indicators
   - Add to library queue

2. **🔗 Add by URL**
   - Paste single video URL
   - Automatically checks for duplicates
   - Adds to library if new

3. **📋 Add by playlist URL**
   - Paste playlist URL
   - Shows summary of new/queued/downloaded videos
   - Batch add all new videos

4. **📚 View/Manage library**
   - View all queued videos
   - Remove individual items
   - Clear entire library

5. **⬇️ Download library**
   - Downloads all queued videos
   - Shows progress bars
   - Automatically moves to download history
   - Clears from queue when complete

6. **⚙️ Settings**
   - Change audio quality (128/192/256/320 kbps)
   - Change download directory

### Status Indicators

- **✓ (Green)** - Already downloaded
- **📥 (Yellow)** - In library queue
- **○ (Cyan)** - New video (not downloaded or queued)

## Project Structure

```
youtube-downloader/
├── main.py              # Main TUI application
├── downloader.py        # Download logic and progress tracking
├── search.py            # YouTube search and metadata
├── utils.py             # Storage and helper functions
├── requirements.txt     # Python dependencies
├── config.json          # User settings (auto-created)
├── library.json         # Download queue (auto-created)
├── downloaded.json      # Download history (auto-created)
└── downloads/           # MP3 files stored here
```

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

Settings are automatically saved when changed through the TUI.

## File Naming

Downloaded files are named: `Artist - Title.mp3`

Example: `Lofi Girl - lofi hip hop radio.mp3`

## Tips

- All downloads are stored in a single folder for easy shuffling
- The app remembers everything you've downloaded, even across sessions
- Downloaded videos are greyed out in search results
- Playlist import shows you which videos are new before adding
- Failed downloads stay in the queue for retry

## Troubleshooting

**"No module named 'yt_dlp'"**
- Run: `pip install -r requirements.txt`

**"ffmpeg not found"**
- Install FFmpeg (see Installation section)

**Slow downloads**
- This is usually due to YouTube throttling
- Try again later or use a VPN

**Search not working**
- Check your internet connection
- YouTube may be blocking requests (rare)

## Legal Notice

This tool is for personal use only. Downloading copyrighted content without permission may be illegal in your jurisdiction. Use responsibly.

## License

Free to use for personal projects.
