"""One-shot playlist downloader to temp folder. No library/downloaded JSON touched."""
from pathlib import Path

import yt_dlp

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL6yWf1f8-MdvCuVd0ahWvnl85t3JxuptA"
OUTPUT_DIR = Path("./temp")
OUTPUT_DIR.mkdir(exist_ok=True)

ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "320",
    }],
    "outtmpl": str(OUTPUT_DIR / "%(uploader)s - %(title)s.%(ext)s"),
    "ignoreerrors": True,
    "no_warnings": False,
}

print(f"Downloading playlist to {OUTPUT_DIR.resolve()} ...")
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([PLAYLIST_URL])
print("Done.")
