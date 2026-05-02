from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import manager
from app.core.cache import cache
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str = "global"):
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
            elif data.get("type") == "subscribe":
                new_channel = data.get("channel", "global")
                await manager.connect(websocket, new_channel)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket, channel)


@router.get("/cache-stats")
async def get_cache_stats():
    """获取缓存统计（用于监控）"""
    return {
        "cache_keys": len(cache._cache) if hasattr(cache, "_cache") else 0,
    }
