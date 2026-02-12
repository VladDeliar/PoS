import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..redis_manager import redis_manager
from ..config import REDIS_CHANNELS

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = None
    listener_task = None

    try:
        try:
            pubsub = await redis_manager.subscribe(REDIS_CHANNELS)

            async def listener(ps):
                async for message in ps.listen():
                    if message["type"] == "message":
                        await websocket.send_text(message["data"])

            listener_task = asyncio.create_task(listener(pubsub))
        except Exception:
            pubsub = None

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
            except WebSocketDisconnect:
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if listener_task:
            listener_task.cancel()
        if pubsub:
            await pubsub.aclose()
