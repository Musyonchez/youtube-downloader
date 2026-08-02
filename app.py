#!/usr/bin/env python3
"""FastAPI web application for YouTube MP3 downloader."""
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router

app = FastAPI(
    title="YouTube MP3 Downloader",
    description="Web-based YouTube audio downloader with thumbnail preview",
    version="2.0.0"
)

# CORS middleware (allow all for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router)


# WebSocket for real-time updates
class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time download progress."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now (can be used for commands later)
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the new landing page."""
    html_file = Path("templates/index.html")
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content="<h1>Template not found</h1>", status_code=404)


@app.get("/old", response_class=HTMLResponse)
async def read_old():
    """Serve the old app page."""
    html_file = Path("templates/old.html")
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content="<h1>Template not found</h1>", status_code=404)


@app.get("/app/{mode}", response_class=HTMLResponse)
async def read_app(mode: str):
    """Serve the app page with different search modes."""
    if mode not in ["name", "playlist", "url"]:
        return HTMLResponse(content="<h1>Invalid mode</h1>", status_code=404)

    html_file = Path("templates/app.html")
    if html_file.exists():
        # Read and render template with mode variable
        with open(html_file) as f:
            content = f.read()
            # Simple template replacement
            content = content.replace("{{ mode }}", mode)
            content = content.replace("{{ mode.title() }}", mode.title())
            content = content.replace("{% if mode == 'name' %}", "")
            content = content.replace("{% elif mode == 'playlist' %}", "")
            content = content.replace("{% else %}", "")
            content = content.replace("{% endif %}", "")

            # Show appropriate text based on mode
            if mode == 'name':
                content = content.replace("Search for videos by name or keyword", "Search for videos by name or keyword")
                content = content.replace("Paste a YouTube playlist URL to download multiple videos", "")
                content = content.replace("Paste a single YouTube video URL", "")
                content = content.replace("Search for videos...", "Search for videos...")
                content = content.replace("Paste playlist URL...", "")
                content = content.replace("Paste video URL...", "")
                content = content.replace("Enter a search term to find videos", "Enter a search term to find videos")
                content = content.replace("Paste a playlist URL to get started", "")
                content = content.replace("Paste a video URL to begin", "")
            elif mode == 'playlist':
                content = content.replace("Search for videos by name or keyword", "")
                content = content.replace("Paste a YouTube playlist URL to download multiple videos", "Paste a YouTube playlist URL to download multiple videos")
                content = content.replace("Paste a single YouTube video URL", "")
                content = content.replace("Search for videos...", "")
                content = content.replace("Paste playlist URL...", "Paste playlist URL...")
                content = content.replace("Paste video URL...", "")
                content = content.replace("Enter a search term to find videos", "")
                content = content.replace("Paste a playlist URL to get started", "Paste a playlist URL to get started")
                content = content.replace("Paste a video URL to begin", "")
            else:  # url
                content = content.replace("Search for videos by name or keyword", "")
                content = content.replace("Paste a YouTube playlist URL to download multiple videos", "")
                content = content.replace("Paste a single YouTube video URL", "Paste a single YouTube video URL")
                content = content.replace("Search for videos...", "")
                content = content.replace("Paste playlist URL...", "")
                content = content.replace("Paste video URL...", "Paste video URL...")
                content = content.replace("Enter a search term to find videos", "")
                content = content.replace("Paste a playlist URL to get started", "")
                content = content.replace("Paste a video URL to begin", "Paste a video URL to begin")

            return HTMLResponse(content=content)
    return HTMLResponse(content="<h1>Template not found</h1>", status_code=404)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting YouTube MP3 Downloader...")
    print("📱 Open http://localhost:8000 in your browser")
    print("🌐 Or access from phone: http://<your-pc-ip>:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
