import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect
from .logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "global"):
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
        logger.debug(f"Client connected to channel: {channel}")

    async def disconnect(self, websocket: WebSocket, channel: str = "global"):
        async with self._lock:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
                if not self.active_connections[channel]:
                    del self.active_connections[channel]
        logger.debug(f"Client disconnected from channel: {channel}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast(self, message: dict, channel: str = "global"):
        async with self._lock:
            connections = self.active_connections.get(channel, set()).copy()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                await self.disconnect(connection, channel)

    async def send_notification(
        self,
        title: str,
        message: str,
        level: str = "info",
        channel: str = "global",
    ):
        notification = {
            "type": "notification",
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(notification, channel)


# 全局连接管理器
manager = ConnectionManager()
