from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.kick.events.webhook_handler import handle_kick_webhook

router = APIRouter(prefix="/kick", tags=["Kick Webhooks"])


@router.post("/webhook")
async def kick_webhook(request: Request):
    return await handle_kick_webhook(request)
