#!/usr/bin/env python3
"""FastAPI web application for YouTube MP3 downloader."""
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes import router
from ws_manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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

templates = Jinja2Templates(directory="templates")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint broadcasting real-time download progress.

    Download progress originates in downloader.py's yt-dlp progress hook,
    which runs in a background-task worker thread; api/routes.py bridges
    that into this connection manager via broadcast_threadsafe.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the landing page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/app/{mode}", response_class=HTMLResponse)
async def read_app(request: Request, mode: str):
    """Serve the app page with different search modes."""
    if mode not in ["name", "playlist", "url"]:
        return HTMLResponse(content="<h1>Invalid mode</h1>", status_code=404)

    return templates.TemplateResponse(request, "app.html", {"mode": mode})


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
