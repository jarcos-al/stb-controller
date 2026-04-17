"""
WebSocket connection manager for real-time state updates.
Handles client connections, broadcasting, and heartbeat.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import WebSocket
from backend.core.logging import get_logger

log = get_logger("websocket")


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._status_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info("ws_client_connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info("ws_client_disconnected", total=len(self.active_connections))

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            log.error("ws_send_failed", error=str(e))
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_status(self, status: dict):
        """Broadcast STB status update to all clients."""
        await self.broadcast({
            "type": "status_update",
            "data": status,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_channel_changed(self, channel_name: str, service_ref: str):
        """Broadcast channel change event."""
        await self.broadcast({
            "type": "channel_changed",
            "data": {
                "channel_name": channel_name,
                "service_ref": service_ref,
            },
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_error(self, error_message: str):
        """Broadcast an error to all clients."""
        await self.broadcast({
            "type": "error",
            "data": {"message": error_message},
            "timestamp": datetime.now().isoformat(),
        })

    async def heartbeat(self):
        """Send periodic heartbeat to all clients."""
        await self.broadcast({
            "type": "heartbeat",
            "data": {},
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Global connection manager instance
ws_manager = ConnectionManager()
