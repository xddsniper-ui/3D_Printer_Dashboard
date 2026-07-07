from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

router = APIRouter()


@router.websocket("/status")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time printer status updates"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass
