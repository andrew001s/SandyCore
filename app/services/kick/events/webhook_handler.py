from __future__ import annotations

import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.config import config
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.client_settings import load_effective_settings, resolve_feature_flags
from app.services.gemini import response_sandy
from app.services.kick.auth import auth
from app.services.moderator import check_banned_words

event_use_case = EventSubUseCase(WebsocketAdapter())


def _header(request: Request, name: str) -> str | None:
    return request.headers.get(name) or request.headers.get(name.lower())


def _extract_payload(raw_body: bytes) -> dict:
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {}


def _extract_event_payload(payload: dict) -> dict:
    for key in ("event", "data", "payload"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _extract_username(event_payload: dict) -> str:
    sender = event_payload.get("sender")
    if isinstance(sender, dict):
        identity = sender.get("identity")
        if isinstance(identity, dict):
            for key in ("username", "name", "display_name", "login"):
                value = identity.get(key)
                if value:
                    return str(value)
        for key in ("username", "name", "display_name", "login"):
            value = sender.get(key)
            if value:
                return str(value)
    for key in ("user_name", "username", "name", "display_name", "login"):
        value = event_payload.get(key)
        if value:
            return str(value)
    return ""


def _extract_message_text(event_payload: dict) -> str:
    for key in ("content", "message", "text"):
        value = event_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    payload = event_payload.get("payload")
    if isinstance(payload, dict):
        for key in ("content", "message", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


async def _resolve_user_id_from_subscription(subscription_id: str | None) -> tuple[str | None, bool]:
    if not subscription_id:
        return None, False
    record = await auth.get_kick_event_subscription(subscription_id)
    if not record:
        return None, False
    return str(record.get("user_id")), bool(record.get("bot", False))


async def handle_kick_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    message_id = _header(request, "Kick-Event-Message-Id")
    timestamp = _header(request, "Kick-Event-Message-Timestamp")
    signature = _header(request, "Kick-Event-Signature")
    event_type = _header(request, "Kick-Event-Type")
    version = _header(request, "Kick-Event-Version")
    subscription_id = _header(request, "Kick-Event-Subscription-Id")

    if not message_id or not timestamp or not event_type or not version:
        raise HTTPException(status_code=400, detail="Missing Kick webhook headers")

    if signature and raw_body and config.KICK_VERIFY_WEBHOOKS:
        valid = await auth.verify_webhook_signature(message_id, timestamp, raw_body, signature)
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid Kick webhook signature")

    payload = _extract_payload(raw_body)
    if isinstance(payload, dict) and payload.get("challenge"):
        return JSONResponse(status_code=200, content={"challenge": payload["challenge"]})

    if event_type != "chat.message.sent":
        return JSONResponse(status_code=200, content={"ok": True})

    event_payload = _extract_event_payload(payload)
    user_id, bot = await _resolve_user_id_from_subscription(subscription_id)
    if not user_id:
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    settings = await load_effective_settings(user_id)
    feature_flags = resolve_feature_flags(settings)
    if not feature_flags.get("chat_replies", True):
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    username = _extract_username(event_payload)
    message_text = _extract_message_text(event_payload)
    if not message_text:
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    bots = {
        "streamlabs",
        "streamelements",
        "nightbot",
        str(settings.get("kick_bot_account") or "").strip().lower(),
        str(settings.get("kick_channel") or "").strip().lower(),
    }
    if username.strip().lower() in {bot_name for bot_name in bots if bot_name}:
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    if await check_banned_words(message_text, user_id):
        return JSONResponse(status_code=200, content={"ok": True, "blocked": True})

    full_message = f"{username}: {message_text}".strip()
    response = await response_sandy(full_message, user_id)
    if not feature_flags.get("voice_replies", True):
        try:
            kick_client = await auth.authenticate_kick(user_id)
            channel_id = (
                event_payload.get("channel_id")
                or event_payload.get("broadcaster_user_id")
                or event_payload.get("room_id")
            )
            await kick_client.send_chat_message(response, str(channel_id) if channel_id else None)
        except Exception as exc:
            print(f"[KICK WEBHOOK] No se pudo responder en chat: {repr(exc)}")
        return JSONResponse(status_code=200, content={"ok": True})

    await event_use_case.handle_events(
        "speech",
        full_message,
        response,
        voice_enabled=True,
    )

    return JSONResponse(status_code=200, content={"ok": True})
