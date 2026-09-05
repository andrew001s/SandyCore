from __future__ import annotations

from typing import Any
from app.services.client_settings import load_effective_settings, save_effective_settings
from app.services.youtube.auth.auth import authenticate_youtube
from app.services.youtube.auth.client import YouTubeAPIClient
from app.services.youtube.lifecycle import _get_state, _resolve_user_id


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_channel_payload(response: dict[str, Any]) -> dict[str, Any]:
    items = response.get("items") or []
    if not items:
        return {}
    return items[0] if isinstance(items[0], dict) else {}


def _extract_live_broadcast(response: dict[str, Any]) -> dict[str, Any]:
    items = response.get("items") or []
    if not items:
        return {}
    return items[0] if isinstance(items[0], dict) else {}


def _extract_live_chat_id(broadcast: dict[str, Any]) -> str:
    snippet = broadcast.get("snippet") or {}
    return _as_text(snippet.get("liveChatId"))


async def _get_client(user_id: str | None = None) -> YouTubeAPIClient:
    resolved = _resolve_user_id(user_id)
    return await authenticate_youtube(resolved)


async def save_channel_context(
    user_id: str | None,
    channel: dict[str, Any],
    broadcast: dict[str, Any] | None = None,
    live_chat_id: str | None = None,
) -> None:
    resolved = _resolve_user_id(user_id)
    payload: dict[str, Any] = {
        "youtube_channel_id": _as_text(channel.get("id")) or None,
        "youtube_channel_title": _as_text((channel.get("snippet") or {}).get("title")) or None,
    }
    if broadcast:
        payload["youtube_broadcast_id"] = _as_text(broadcast.get("id")) or None
    if live_chat_id:
        payload["youtube_live_chat_id"] = _as_text(live_chat_id) or None
    await save_effective_settings(payload, resolved)


async def get_profile_users(bot: bool = False, user_id: str | None = None) -> dict[str, Any]:
    _ = bot
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    channel = await client.get_channel()
    if not channel:
        raise Exception("No existe un canal de YouTube autenticado para este usuario")

    settings = await load_effective_settings(resolved)
    broadcast_id = _as_text(settings.get("youtube_broadcast_id")) or None
    live_chat_id = _as_text(settings.get("youtube_live_chat_id")) or None
    await save_channel_context(
        resolved,
        channel,
        {"id": broadcast_id} if broadcast_id else None,
        live_chat_id,
    )
    snippet = channel.get("snippet") or {}
    statistics = channel.get("statistics") or {}
    content_details = channel.get("contentDetails") or {}
    return {
        "id": channel.get("id"),
        "username": snippet.get("title") or snippet.get("customUrl") or "",
        "email": "",
        "picProfile": (
            (snippet.get("thumbnails") or {}).get("high")
            or (snippet.get("thumbnails") or {}).get("default")
            or {}
        ).get("url", ""),
        "channel_title": snippet.get("title"),
        "custom_url": snippet.get("customUrl"),
        "description": snippet.get("description"),
        "subscriber_count": statistics.get("subscriberCount"),
        "view_count": statistics.get("viewCount"),
        "video_count": statistics.get("videoCount"),
        "uploads_playlist_id": (content_details.get("relatedPlaylists") or {}).get("uploads"),
        "live_chat_id": live_chat_id or None,
        "broadcast_id": broadcast_id,
    }


async def list_broadcasts(
    user_id: str | None = None, broadcast_status: str = "active"
) -> dict[str, Any]:
    client = await _get_client(user_id)
    return await client.list_broadcasts(broadcast_status=broadcast_status)


async def get_stats(user_id: str | None = None) -> dict[str, Any]:
    client = await _get_client(user_id)
    return await client.get_stats()


async def update_broadcast(
    user_id: str | None = None, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    settings = await load_effective_settings(resolved)
    data = payload or {}
    broadcast_id = _as_text(data.get("broadcast_id")) or _as_text(
        settings.get("youtube_broadcast_id")
    )
    if not broadcast_id:
        broadcasts = await client.list_broadcasts(broadcast_status="active")
        broadcast = _extract_live_broadcast(broadcasts or {})
        broadcast_id = _as_text(broadcast.get("id"))
    if not broadcast_id:
        raise Exception("No hay una transmisión activa para actualizar")

    update_payload = {
        "title": data.get("title"),
        "description": data.get("description"),
        "privacyStatus": data.get("privacy_status"),
        "enableMonitorStream": data.get("enable_monitor_stream"),
        "broadcastStreamDelayMs": data.get("broadcast_stream_delay_ms"),
        "scheduledStartTime": data.get("scheduled_start_time"),
        "scheduledEndTime": data.get("scheduled_end_time"),
    }
    response = await client.update_live_broadcast(broadcast_id, update_payload)
    broadcast = _extract_live_broadcast({"items": [response]})
    live_chat_id = _extract_live_chat_id(broadcast)
    await save_channel_context(
        resolved, (await client.get_channel()), broadcast, live_chat_id or None
    )
    return response


async def transition_broadcast(
    user_id: str | None = None, broadcast_id: str | None = None, status: str = "live"
) -> dict[str, Any]:
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    settings = await load_effective_settings(resolved)
    current_broadcast_id = _as_text(broadcast_id) or _as_text(settings.get("youtube_broadcast_id"))
    if not current_broadcast_id:
        broadcasts = await client.list_broadcasts(broadcast_status="all")
        items = (broadcasts or {}).get("items") or []
        if items:
            current_broadcast_id = _as_text(items[0].get("id"))
    if not current_broadcast_id:
        raise Exception("No hay una transmisión de YouTube para cambiar de estado")

    response = await client.transition_live_broadcast(current_broadcast_id, status)
    broadcast = _extract_live_broadcast({"items": [response]})
    live_chat_id = _extract_live_chat_id(broadcast)
    await save_channel_context(
        resolved, (await client.get_channel()), broadcast, live_chat_id or None
    )
    return response


async def send_chat_message(
    user_id: str | None = None, live_chat_id: str | None = None, message: str = ""
) -> Any:
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    settings = await load_effective_settings(resolved)
    state = await _get_state(resolved)
    chat_id = (
        _as_text(live_chat_id)
        or _as_text(state.live_chat_id)
        or _as_text(settings.get("youtube_live_chat_id"))
    )
    if not chat_id:
        raise Exception(
            "No hay live chat configurado para enviar el mensaje. "
            "Primero inicia el servicio o guarda youtube_live_chat_id."
        )

    res = await client.send_chat_message(chat_id, message)
    if state.monitor and isinstance(res, dict) and res.get("id"):
        state.monitor.handler.record_sent_message(res.get("id"))
    return res
