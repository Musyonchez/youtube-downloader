# FFmpeg Conversion Bug — 2026-08-03

User noticed downloaded files in `downloads/` weren't playable and asked to check them.

## Diagnosis

Three files in `downloads/` had no file extension at all (e.g. `Kygo - Kygo & Selena Gomez - It Ain't Me (Audio)`, no `.mp3`). Inspecting the raw bytes showed an EBML header with `webm` as the DocType -- these were raw WebM downloads, not MP3s, despite living under a filename that looked like a finished download.

Root causes, both in [app/services/downloader.py](../app/services/downloader.py):

1. **FFmpeg wasn't installed on this machine at all** (`which ffmpeg` found nothing). `download_audio()` uses yt-dlp's `FFmpegExtractAudio` postprocessor to convert the downloaded audio to MP3; without FFmpeg, that step throws, the exception is caught, and the download is correctly reported as failed (these 3 files were never recorded in `data/downloads.db` -- confirmed the count was unaffected). So the app "knew" these failed.
2. **But `ydl_opts['outtmpl']` had no `%(ext)s` placeholder.** Without it, yt-dlp writes the raw pre-conversion download to the *exact literal* `outtmpl` path -- no extension appended at all. Combined with (1), a failed conversion left the raw WebM audio sitting under a filename with no extension, which a user (or the app) could easily mistake for a finished download that just needs an extension, rather than an incomplete/failed one.
3. **The orphaned raw file was never cleaned up** on failure -- `download_audio()`'s `except` block logged the error and returned `None`, but didn't touch whatever partial file yt-dlp had already written to disk.

## Fixes

- `outtmpl` now ends in `.%(ext)s`, so yt-dlp writes intermediate files with their real extension (e.g. `.webm`) instead of a bare, extension-less name that's indistinguishable from a real MP3 at a glance.
- `download_audio()` now checks `shutil.which('ffmpeg')` up front and fails fast with a clear message (`FFmpeg not found on PATH -- required to convert downloads to MP3. Install it (e.g. \`winget install Gyan.FFmpeg\` on Windows, \`sudo apt install ffmpeg\` on Debian/Ubuntu) and restart the app.`) instead of downloading the full audio stream first and only then discovering FFmpeg is missing during postprocessing.
- On any download failure, `_cleanup_partial_download()` globs `download_dir` for `{base_name}.*` and removes whatever raw/partial file was left behind, so failures don't silently accumulate disk-eating junk that looks like it might be real downloads.
- README's FFmpeg install section now includes Windows (`winget install Gyan.FFmpeg`) -- it previously only listed Arch/Ubuntu/macOS.

## What was done about this specific machine

- Installed FFmpeg via `winget install Gyan.FFmpeg` (confirmed with the user first, since it modifies the system).
- Moved the 3 broken files to `downloads/_failed/` with their correct `.webm` extension restored, rather than deleting them (confirmed with the user first) -- nothing lost, just out of the way of the real MP3 library.

## Verification

- Fast-fail path: queued a real video with FFmpeg deliberately not on `PATH`, confirmed the download attempt fails immediately with the clear error message (visible in server logs, no crash), the item is removed from the queue, and no file is left in `downloads/`.
- Success path: with FFmpeg reachable, queued and downloaded a real video end-to-end through the live server. Confirmed via `data/downloads.db` count (655 -> 656) and by inspecting the resulting file's raw bytes: genuine `ID3` header, `TIT2`/`TPE1` tags correctly set to the video's title/channel. Cleaned up this test download (file + db row) afterward since it wasn't a real user request.
- Also incidentally confirmed the `sys.stdout.reconfigure` fix from earlier ([04-file-reorg.md](04-file-reorg.md)) correctly covers `downloader.py`'s `rich.Console` prints too -- a standalone script that imports `downloader.py` directly (bypassing `app/main.py`'s `__main__` guard) crashed with the same `UnicodeEncodeError` class of bug when printing the ✗ error symbol on this machine's cp1252 console, but the real app path (`python -m app.main`) does not, since the reconfigure runs before any request handling.
