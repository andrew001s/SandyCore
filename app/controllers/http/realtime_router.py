import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.security.stream_token import create_stream_token, verify_stream_token
from app.controllers.websocket.websocket_server import manager

router = APIRouter(tags=["Realtime"])


@router.get("/stream/token")
async def create_realtime_token(current_user: ClerkUser = Depends(verify_clerk_session)):
    token = create_stream_token(current_user.user_id)
    return JSONResponse(
        status_code=200,
        content={
            "token": token,
            "expiresIn": 300,
            "streamUrl": "/stream",
        },
    )


def _format_sse(event_name: str, payload: dict[str, Any]) -> str:
    return (
        f"event: {event_name}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


@router.get("/stream")
async def stream_events(request: Request, token: str = Query(...)):
    payload = verify_stream_token(token)
    user_id = str(payload["sub"])
    queue = await manager.connect_stream(user_id)

    async def event_generator():
        try:
            yield _format_sse(
                "system",
                {
                    "id": "stream_connected",
                    "type": "system",
                    "message": "Stream conectado",
                    "metadata": {"source": "realtime", "userId": user_id},
                },
            )

            while True:
                if await request.is_disconnected():
                    break

                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    event_name = str(message.get("type", "message"))
                    yield _format_sse(event_name, message)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await manager.disconnect_stream(queue, user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
