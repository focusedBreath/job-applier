import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.utils.logging import broadcaster

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/log")
async def log_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = broadcaster.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_text(msg)
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_text('{"event":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unsubscribe(queue)
