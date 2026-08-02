"""WebSocket connection manager for real-time download progress."""
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts JSON messages to all of them."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    def broadcast_threadsafe(self, message: dict, loop: asyncio.AbstractEventLoop):
        """Schedule a broadcast from a worker thread (e.g. a BackgroundTasks callable, which
        FastAPI runs in a threadpool rather than on the event loop)."""
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)
        except RuntimeError:
            logger.warning("Could not broadcast WebSocket message: event loop unavailable")


manager = ConnectionManager()
