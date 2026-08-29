from __future__ import annotations

import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.config import config
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.avatar_events import build_system_event
from app.services.client_settings import load_effective_settings, resolve_feature_flags
from app.services.gemini import (
    response_gemini_events,
    response_gemini_rewards,
    response_sandy,
    should_delete_message,
)
from app.services.kick.auth import auth
from app.services.moderator import check_banned_words

event_use_case = EventSubUseCase(WebsocketAdapter())
websocket_adapter = WebsocketAdapter()


def _log_webhook(event: str, **fields) -> None:
    safe_fields = ", ".join(f"{key}={value}" for key, value in fields.items())
    print(f"[KICK WEBHOOK] {event}" + (f" | {safe_fields}" if safe_fields else ""))


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


def _extract_message_id(event_payload: dict) -> str:
    value = event_payload.get("message_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    value = event_payload.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _extract_first_string(event_payload: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = event_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_actor_name(event_payload: dict) -> str:
    candidates = (
        "sender",
        "follower",
        "subscriber",
        "gifter",
        "user",
        "banned_user",
        "moderator",
        "broadcaster",
    )
    for key in candidates:
        value = event_payload.get(key)
        if isinstance(value, dict):
            identity = value.get("identity")
            if isinstance(identity, dict):
                for identity_key in ("username", "name", "display_name", "login", "slug"):
                    identity_value = identity.get(identity_key)
                    if identity_value:
                        return str(identity_value)
            for field in ("username", "name", "display_name", "login", "slug"):
                field_value = value.get(field)
                if field_value:
                    return str(field_value)
        elif isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("user_name", "username", "name", "display_name", "login", "slug"):
        value = event_payload.get(key)
        if value:
            return str(value)
    return ""


def _extract_livestream_status(event_payload: dict) -> str:
    for key in ("status", "state", "livestream_status", "stream_status"):
        value = event_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    is_live = event_payload.get("is_live")
    if isinstance(is_live, bool):
        return "live" if is_live else "offline"
    return "updated"


def _extract_gift_amount(event_payload: dict) -> str:
    for key in ("amount", "kicks", "count", "quantity", "value"):
        value = event_payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _extract_reward_title(event_payload: dict) -> str:
    reward = event_payload.get("reward")
    if isinstance(reward, dict):
        for key in ("title", "name", "id"):
            value = reward.get(key)
            if value:
                return str(value)
    return _extract_first_string(event_payload, ("title", "name", "reward_name", "reward"))


async def _broadcast_system_notification(user_id: str, message: str, metadata: dict) -> None:
    await websocket_adapter.broadcast_message(
        build_system_event(
            message,
            metadata={
                "source": "kick_webhook",
                "user_id": user_id,
                **metadata,
            },
        ),
        user_id,
    )


async def _handle_non_chat_event(
    event_type: str,
    event_payload: dict,
    user_id: str,
) -> JSONResponse:
    actor = _extract_actor_name(event_payload)
    settings = await load_effective_settings(user_id)

    if event_type == "channel.followed":
        message = f"Kick follow: {actor or 'usuario desconocido'}"
        response = await response_gemini_events(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "channel.subscription.new":
        message = f"Kick new subscriber: {actor or 'usuario desconocido'}"
        response = await response_gemini_events(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "channel.subscription.renewal":
        message = f"Kick resub: {actor or 'usuario desconocido'}"
        response = await response_gemini_events(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "channel.subscription.gifts":
        message = f"Kick gifted subs: {actor or 'usuario desconocido'}"
        response = await response_gemini_events(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "channel.reward.redemption.updated":
        reward_title = _extract_reward_title(event_payload)
        message = f"Kick reward redemption: {reward_title or 'recompensa'} by {actor or 'usuario desconocido'}"
        response = await response_gemini_rewards(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "kicks.gifted":
        amount = _extract_gift_amount(event_payload)
        gift_name = _extract_first_string(event_payload, ("name", "type", "label", "title"))
        message = f"Kick gifted: {amount or '0'} {gift_name or 'kicks'} by {actor or 'usuario desconocido'}"
        response = await response_gemini_rewards(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "moderation.banned":
        reason = _extract_first_string(event_payload, ("reason", "message", "moderation_reason"))
        message = f"Kick moderation banned: {actor or 'usuario desconocido'}"
        if reason:
            message = f"{message} reason: {reason}"
        response = await response_gemini_events(message, user_id)
        await event_use_case.handle_events("reaction", message, response, user_id=user_id, voice_enabled=False)
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "livestream.status.updated":
        status = _extract_livestream_status(event_payload)
        message = "Kick stream live" if status == "live" else "Kick stream offline" if status == "offline" else f"Kick stream status updated: {status}"
        await _broadcast_system_notification(
            user_id,
            message,
            {
                "eventType": event_type,
                "status": status,
            },
        )
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    if event_type == "livestream.metadata.updated":
        title = _extract_first_string(event_payload, ("title", "stream_title"))
        category = _extract_first_string(event_payload, ("category", "category_name", "category_title"))
        message = "Kick stream metadata updated"
        if title or category:
            details = ", ".join(part for part in [f"title={title}" if title else "", f"category={category}" if category else ""] if part)
            message = f"{message}: {details}"
        await _broadcast_system_notification(
            user_id,
            message,
            {
                "eventType": event_type,
                "title": title,
                "category": category,
            },
        )
        return JSONResponse(status_code=200, content={"ok": True, "handled": event_type})

    _log_webhook(
        "unhandled_event",
        event_type=event_type,
        subscription_id="n/a",
        bot=False,
        configured_channel=str(settings.get("kick_channel") or ""),
    )
    return JSONResponse(status_code=200, content={"ok": True, "ignored": True})


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

    _log_webhook(
        "received",
        event_type=event_type,
        subscription_id=subscription_id or "missing",
        message_id=message_id,
        signature_present=bool(signature),
        verify_signatures=config.KICK_VERIFY_WEBHOOKS,
    )

    if signature and raw_body and config.KICK_VERIFY_WEBHOOKS:
        valid = await auth.verify_webhook_signature(message_id, timestamp, raw_body, signature)
        _log_webhook(
            "signature_checked",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            signature_valid=valid,
        )
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid Kick webhook signature")
    elif not config.KICK_VERIFY_WEBHOOKS:
        _log_webhook(
            "signature_skipped",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
        )
    else:
        _log_webhook(
            "signature_missing",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
        )

    payload = _extract_payload(raw_body)
    if isinstance(payload, dict) and payload.get("challenge"):
        _log_webhook(
            "challenge",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
        )
        return JSONResponse(status_code=200, content={"challenge": payload["challenge"]})

    event_payload = _extract_event_payload(payload)
    user_id, bot = await _resolve_user_id_from_subscription(subscription_id)
    if not user_id:
        _log_webhook(
            "subscription_not_found",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
        )
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    if event_type != "chat.message.sent":
        _log_webhook(
            "event_route",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
        )
        return await _handle_non_chat_event(event_type, event_payload, user_id)

    settings = await load_effective_settings(user_id)
    feature_flags = resolve_feature_flags(settings)
    username = _extract_username(event_payload)
    message_id = _extract_message_id(event_payload)
    message_text = _extract_message_text(event_payload)
    if not message_text:
        _log_webhook(
            "empty_message",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
        )
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    bots = {
        "streamlabs",
        "streamelements",
        "nightbot",
        str(settings.get("kick_bot_account") or "").strip().lower(),
        str(settings.get("kick_channel") or "").strip().lower(),
    }
    if username.strip().lower() in {bot_name for bot_name in bots if bot_name}:
        _log_webhook(
            "ignored_bot_message",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
        )
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    kick_client = await auth.authenticate_kick(user_id)

    # El diccionario solo levanta la sospecha: quien decide borrar es la IA, igual
    # que en Twitch. Antes bastaba con que la palabra apareciera, así que un
    # "qué idiota soy, jaja" se borraba sin más.
    if await check_banned_words(message_text, user_id) and await should_delete_message(
        message_text, user_id
    ):
        _log_webhook(
            "blocked_banned_words",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
            message_id=message_id or "missing",
        )
        try:
            if message_id:
                await kick_client.delete_chat_message(message_id)
                _log_webhook(
                    "deleted_message",
                    event_type=event_type,
                    subscription_id=subscription_id or "missing",
                    bot=bot,
                    message_id=message_id,
                )
        except Exception as exc:
            print(f"[KICK WEBHOOK] No se pudo borrar el mensaje: {repr(exc)}")

        warning_message = (
            f"@{username} tu mensaje fue eliminado por moderación. "
            "Evita usar palabras prohibidas."
        ).strip()
        try:
            channel_id = (
                event_payload.get("channel_id")
                or event_payload.get("broadcaster_user_id")
                or event_payload.get("room_id")
            )
            await kick_client.send_chat_message(
                warning_message,
                str(channel_id) if channel_id else None,
            )
            _log_webhook(
                "warning_sent",
                event_type=event_type,
                subscription_id=subscription_id or "missing",
                bot=bot,
                message_id=message_id or "missing",
            )
        except Exception as exc:
            print(f"[KICK WEBHOOK] No se pudo enviar advertencia: {repr(exc)}")

        return JSONResponse(status_code=200, content={"ok": True, "blocked": True})

    if not feature_flags.get("chat_replies", True):
        _log_webhook(
            "chat_replies_disabled",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
        )
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    _log_webhook(
        "processing_chat_message",
        event_type=event_type,
        subscription_id=subscription_id or "missing",
        bot=bot,
        reply_mode="voice" if feature_flags.get("voice_replies", True) else "chat",
    )
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
        _log_webhook(
            "chat_replied",
            event_type=event_type,
            subscription_id=subscription_id or "missing",
            bot=bot,
        )
        return JSONResponse(status_code=200, content={"ok": True})

    await event_use_case.handle_events(
        "speech",
        full_message,
        response,
        user_id=user_id, voice_enabled=True,
    )
    _log_webhook(
        "speech_dispatched",
        event_type=event_type,
        subscription_id=subscription_id or "missing",
        bot=bot,
    )

    return JSONResponse(status_code=200, content={"ok": True})
