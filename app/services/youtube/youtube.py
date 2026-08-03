from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.avatar_events import build_system_event
from app.services.client_settings import load_effective_settings, resolve_feature_flags
from app.services.gemini import response_gemini_events, response_gemini_rewards, response_sandy
from app.services.moderator import check_banned_words
from app.services.youtube.auth.auth import (
    YouTubeAPIClient,
    authenticate_youtube,
    get_google_oauth_token,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_user_id(user_id: str | None = None) -> str:
    from app.core.runtime import get_active_user_id

    resolved = user_id or get_active_user_id()
    if not resolved:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return str(resolved)


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


def _extract_bots(settings: dict[str, Any], channel: dict[str, Any]) -> set[str]:
    bots = {
        _as_text(settings.get("youtube_bot_account")).lower(),
        _as_text(settings.get("youtube_channel_title")).lower(),
        _as_text(channel.get("snippet", {}).get("title")).lower(),
    }
    return {bot for bot in bots if bot}


def _extract_author_details(message: dict[str, Any]) -> dict[str, Any]:
    author_details = message.get("authorDetails")
    if isinstance(author_details, dict):
        return author_details
    return {}


def _extract_message_snippet(message: dict[str, Any]) -> dict[str, Any]:
    snippet = message.get("snippet")
    if isinstance(snippet, dict):
        return snippet
    return {}


def _extract_text_message(snippet: dict[str, Any]) -> str:
    text_details = snippet.get("textMessageDetails")
    if isinstance(text_details, dict):
        message_text = text_details.get("messageText")
        if isinstance(message_text, str) and message_text.strip():
            return message_text.strip()
    display_message = snippet.get("displayMessage")
    if isinstance(display_message, str) and display_message.strip():
        return display_message.strip()
    return ""


def _extract_message_type(snippet: dict[str, Any]) -> str:
    value = snippet.get("type")
    return _as_text(value)


def _extract_message_id(message: dict[str, Any]) -> str:
    return _as_text(message.get("id"))


def _extract_author_name(author_details: dict[str, Any]) -> str:
    for key in ("displayName", "channelId", "channelUrl"):
        value = author_details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_super_chat_message(snippet: dict[str, Any]) -> str:
    details = snippet.get("superChatDetails")
    if isinstance(details, dict):
        amount = _as_text(details.get("amountDisplayString") or details.get("amountMicros"))
        currency = _as_text(details.get("currency"))
        comment = _as_text(details.get("userComment"))
        tier = _as_text(details.get("tier"))
        parts = [part for part in [amount, currency, f"tier={tier}" if tier else "", comment] if part]
        return "Super Chat: " + " | ".join(parts) if parts else "Super Chat"
    return "Super Chat"


def _extract_super_sticker_message(snippet: dict[str, Any]) -> str:
    details = snippet.get("superStickerDetails")
    if isinstance(details, dict):
        sticker = _as_text(details.get("superStickerMetadata", {}).get("altText"))
        amount = _as_text(details.get("amountDisplayString") or details.get("amountMicros"))
        parts = [part for part in [amount, sticker] if part]
        return "Super Sticker: " + " | ".join(parts) if parts else "Super Sticker"
    return "Super Sticker"


def _extract_membership_message(snippet: dict[str, Any]) -> str:
    if snippet.get("membershipGiftingDetails"):
        return "Membership gifting"
    if snippet.get("giftMembershipReceivedDetails"):
        return "Gift membership received"
    if snippet.get("newSponsorDetails"):
        return "New sponsor"
    return "Membership event"


@dataclass
class YouTubeLifecycleState:
    armed: bool = False
    running: bool = False
    last_activity: datetime = field(default_factory=_utcnow)
    monitor_task: asyncio.Task | None = None
    last_known_live: bool | None = None
    live_chat_id: str | None = None
    broadcast_id: str | None = None
    next_page_token: str | None = None


_states: dict[str, YouTubeLifecycleState] = {}
_state_lock = asyncio.Lock()
_monitor_interval_seconds = 10
_websocket_adapter = WebsocketAdapter()
_event_use_case = EventSubUseCase(_websocket_adapter)


async def _get_state(user_id: str | None) -> YouTubeLifecycleState:
    resolved = _resolve_user_id(user_id)
    async with _state_lock:
        state = _states.get(resolved)
        if state is None:
            state = YouTubeLifecycleState()
            _states[resolved] = state
        return state


async def mark_activity(user_id: str | None = None) -> None:
    state = await _get_state(user_id)
    state.last_activity = _utcnow()


async def _broadcast_system_notification(user_id: str, message: str, metadata: dict[str, Any]) -> None:
    await _websocket_adapter.broadcast_message(
        build_system_event(
            message,
            metadata={
                "source": "youtube",
                "user_id": user_id,
                **metadata,
            },
        )
    )


async def _get_client(user_id: str | None = None) -> YouTubeAPIClient:
    resolved = _resolve_user_id(user_id)
    return await authenticate_youtube(resolved)


async def _get_channel_and_broadcast(
    user_id: str | None = None,
) -> tuple[YouTubeAPIClient, dict[str, Any], dict[str, Any], str]:
    client = await _get_client(user_id)
    settings = await load_effective_settings(_resolve_user_id(user_id))
    channel = _extract_channel_payload(await client.request_json(
        "GET",
        "/channels",
        params={"part": "snippet,statistics,contentDetails,brandingSettings", "mine": "true", "maxResults": "1"},
    ))
    if not channel:
        raise Exception("No se pudo obtener el canal de YouTube autenticado")

    broadcast: dict[str, Any] = {}
    live_chat_id = ""
    try:
        broadcasts = await client.list_broadcasts(broadcast_status="active")
        broadcast = _extract_live_broadcast(broadcasts or {})
        live_chat_id = _extract_live_chat_id(broadcast)
    except Exception as exc:
        print(f"[YOUTUBE] No se pudo listar transmisiones activas: {repr(exc)}")

    if live_chat_id:
        await save_channel_context(user_id, channel, broadcast, live_chat_id)
    elif settings.get("youtube_live_chat_id"):
        live_chat_id = _as_text(settings.get("youtube_live_chat_id"))

    return client, channel, broadcast, live_chat_id


async def save_channel_context(
    user_id: str | None,
    channel: dict[str, Any],
    broadcast: dict[str, Any] | None = None,
    live_chat_id: str | None = None,
) -> None:
    from app.services.client_settings import save_effective_settings

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


async def get_profile_users(bot: bool = False, user_id: str | None = None):
    _ = bot
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    channel = _extract_channel_payload(
        await client.request_json(
            "GET",
            "/channels",
            params={"part": "snippet,statistics,contentDetails,brandingSettings", "mine": "true", "maxResults": "1"},
        )
    )
    if not channel:
        raise Exception("No existe un canal de YouTube autenticado para este usuario")

    broadcast: dict[str, Any] = {}
    live_chat_id = ""
    try:
        broadcasts = await client.list_broadcasts(broadcast_status="active")
        broadcast = _extract_live_broadcast(broadcasts or {})
        live_chat_id = _extract_live_chat_id(broadcast)
    except Exception as exc:
        print(f"[YOUTUBE] No se pudo resolver broadcast activo para perfil: {repr(exc)}")

    await save_channel_context(resolved, channel, broadcast, live_chat_id or None)
    snippet = channel.get("snippet") or {}
    statistics = channel.get("statistics") or {}
    content_details = channel.get("contentDetails") or {}
    return {
        "id": channel.get("id"),
        "username": snippet.get("title") or snippet.get("customUrl") or "",
        "email": "",
        "picProfile": ((snippet.get("thumbnails") or {}).get("high") or (snippet.get("thumbnails") or {}).get("default") or {}).get("url", ""),
        "channel_title": snippet.get("title"),
        "custom_url": snippet.get("customUrl"),
        "description": snippet.get("description"),
        "subscriber_count": statistics.get("subscriberCount"),
        "view_count": statistics.get("viewCount"),
        "video_count": statistics.get("videoCount"),
        "uploads_playlist_id": (content_details.get("relatedPlaylists") or {}).get("uploads"),
        "live_chat_id": live_chat_id or None,
        "broadcast_id": broadcast.get("id"),
    }


async def get_tokens(user_id: str | None = None, bot: bool = False):
    _ = bot
    resolved = _resolve_user_id(user_id)
    token = await get_google_oauth_token(resolved)
    return {
        "provider": "google",
        "authenticated": bool(token.get("token")),
        "user_id": resolved,
        "label": token.get("label"),
        "expires_at": token.get("expiresAt"),
        "scopes": token.get("scopes") or [],
    }


async def start_services(user_id: str | None = None) -> None:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)
    client, channel, broadcast, live_chat_id = await _get_channel_and_broadcast(resolved)
    if not live_chat_id:
        raise Exception("No hay una transmisión activa de YouTube con chat disponible")

    state.running = True
    state.armed = True
    state.last_known_live = True
    state.broadcast_id = broadcast.get("id") or state.broadcast_id
    state.live_chat_id = live_chat_id
    state.next_page_token = None
    await save_channel_context(resolved, channel, broadcast, live_chat_id)
    await mark_activity(resolved)

    if state.monitor_task and not state.monitor_task.done():
        return
    state.monitor_task = asyncio.create_task(_monitor_loop(resolved))


async def stop_services(user_id: str | None = None) -> None:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)
    state.running = False
    state.armed = False
    task = state.monitor_task
    print(f"[YOUTUBE LIFECYCLE] Deteniendo monitor para {resolved}")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    state.monitor_task = None


async def _handle_chat_message(
    client: YouTubeAPIClient,
    user_id: str,
    message: dict[str, Any],
    settings: dict[str, Any],
    channel: dict[str, Any],
    live_chat_id: str,
) -> None:
    feature_flags = resolve_feature_flags(settings)
    snippet = _extract_message_snippet(message)
    author = _extract_author_details(message)
    message_text = _extract_text_message(snippet)
    message_type = _extract_message_type(snippet)
    message_id = _extract_message_id(message)
    author_name = _extract_author_name(author)
    bots = _extract_bots(settings, channel)
    author_id = _as_text(author.get("channelId")).lower()

    if not message_text:
        return

    if author_name.lower() in bots or (
        author_id and author_id == _as_text(channel.get("id")).lower()
    ):
        return

    if await check_banned_words(message_text, user_id) and not (
        author.get("isChatModerator") or author.get("isChatOwner")
    ):
        try:
            if message_id:
                await client.delete_chat_message(message_id)
        except Exception as exc:
            print(f"[YOUTUBE WEBHOOK] No se pudo borrar el mensaje: {repr(exc)}")

        warning_message = (
            f"@{author_name or 'usuario'} tu mensaje fue eliminado por moderación. "
            "Evita usar palabras prohibidas."
        ).strip()
        try:
            await client.send_chat_message(live_chat_id, warning_message)
        except Exception as exc:
            print(f"[YOUTUBE WEBHOOK] No se pudo enviar advertencia: {repr(exc)}")
        return

    full_message = f"{author_name or 'Usuario'}: {message_text}".strip()

    if message_type == "textMessageEvent":
        if not feature_flags.get("chat_replies", True):
            return
        response = await response_sandy(full_message, user_id)
        if not feature_flags.get("voice_replies", True):
            try:
                await client.send_chat_message(live_chat_id, response)
            except Exception as exc:
                print(f"[YOUTUBE WEBHOOK] No se pudo responder en chat: {repr(exc)}")
            return

        await _event_use_case.handle_events(
            "speech",
            full_message,
            response,
            voice_enabled=True,
        )
        return

    if message_type in {"superChatEvent", "superStickerEvent", "membershipGiftingEvent", "giftMembershipReceivedEvent"}:
        if not feature_flags.get("rewards", True):
            return
        response = await response_gemini_rewards(full_message, user_id)
        await _event_use_case.handle_events(
            "reaction",
            full_message,
            response,
            voice_enabled=False,
        )
        return

    if message_type in {"newSponsorEvent", "userBannedEvent"}:
        if not feature_flags.get("events", True):
            return
        response = await response_gemini_events(full_message, user_id)
        await _event_use_case.handle_events(
            "reaction",
            full_message,
            response,
            voice_enabled=False,
        )
        return


async def _poll_live_chat(user_id: str) -> None:
    state = await _get_state(user_id)
    settings = await load_effective_settings(user_id)
    client = await _get_client(user_id)

    while True:
        state = await _get_state(user_id)
        if not state.running or not state.armed:
            break

        live_chat_id = state.live_chat_id or _as_text(settings.get("youtube_live_chat_id"))
        if not live_chat_id:
            try:
                _, channel, broadcast, live_chat_id = await _get_channel_and_broadcast(user_id)
                state.live_chat_id = live_chat_id
                state.broadcast_id = broadcast.get("id") or state.broadcast_id
            except Exception as exc:
                print(f"[YOUTUBE POLL] No se pudo resolver el live chat: {repr(exc)}")
                await asyncio.sleep(_monitor_interval_seconds)
                continue

        try:
            response = await client.get_live_chat_messages(
                live_chat_id,
                page_token=state.next_page_token,
                max_results=200,
            )
            items = response.get("items") or []
            state.next_page_token = response.get("nextPageToken") or state.next_page_token
            polling_interval_ms = int(response.get("pollingIntervalMillis") or (_monitor_interval_seconds * 1000))
            if items:
                resolved_channel = _extract_channel_payload(
                    await client.request_json(
                        "GET",
                        "/channels",
                        params={"part": "snippet,statistics,contentDetails,brandingSettings", "mine": "true", "maxResults": "1"},
                    )
                )
                for item in items:
                    await _handle_chat_message(
                        client,
                        user_id,
                        item if isinstance(item, dict) else {},
                        settings,
                        resolved_channel,
                        live_chat_id,
                    )
            await asyncio.sleep(max(1, polling_interval_ms / 1000))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[YOUTUBE POLL] Error en monitor de {user_id}: {repr(exc)}")
            await asyncio.sleep(_monitor_interval_seconds)


async def _monitor_loop(user_id: str) -> None:
    try:
        await _poll_live_chat(user_id)
    finally:
        state = await _get_state(user_id)
        state.monitor_task = None


async def get_service_status(user_id: str | None = None) -> dict[str, object]:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)
    settings = await load_effective_settings(resolved)
    last_activity = state.last_activity.isoformat() if state.last_activity else None
    return {
        "user_id": resolved,
        "running": state.running,
        "armed": state.armed,
        "monitor_active": bool(state.monitor_task and not state.monitor_task.done()),
        "last_known_live": state.last_known_live,
        "last_activity": last_activity,
        "youtube_channel_id": settings.get("youtube_channel_id"),
        "youtube_channel_title": settings.get("youtube_channel_title"),
        "youtube_broadcast_id": state.broadcast_id or settings.get("youtube_broadcast_id"),
        "youtube_live_chat_id": state.live_chat_id or settings.get("youtube_live_chat_id"),
        "status": "active" if state.running else "inactive",
    }


async def list_broadcasts(user_id: str | None = None, broadcast_status: str = "active") -> dict[str, Any]:
    client = await _get_client(user_id)
    return await client.list_broadcasts(broadcast_status=broadcast_status)


async def get_stats(user_id: str | None = None) -> dict[str, Any]:
    client = await _get_client(user_id)
    return await client.get_stats()


async def update_broadcast(user_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = _resolve_user_id(user_id)
    client = await _get_client(resolved)
    settings = await load_effective_settings(resolved)
    data = payload or {}
    broadcast_id = _as_text(data.get("broadcast_id")) or _as_text(settings.get("youtube_broadcast_id"))
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
    await save_channel_context(resolved, (await client.get_channel()), broadcast, live_chat_id or None)
    return response


async def send_chat_message(user_id: str | None = None, live_chat_id: str | None = None, message: str = "") -> Any:
    client = await _get_client(user_id)
    resolved = _resolve_user_id(user_id)
    settings = await load_effective_settings(resolved)
    chat_id = _as_text(live_chat_id) or _as_text(settings.get("youtube_live_chat_id"))
    if not chat_id:
        broadcasts = await client.list_broadcasts(broadcast_status="active")
        broadcast = _extract_live_broadcast(broadcasts or {})
        chat_id = _extract_live_chat_id(broadcast)
    if not chat_id:
        raise Exception("No hay live chat activo para enviar el mensaje")
    return await client.send_chat_message(chat_id, message)


async def transition_broadcast(user_id: str | None = None, broadcast_id: str | None = None, status: str = "live") -> dict[str, Any]:
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
    await save_channel_context(resolved, (await client.get_channel()), broadcast, live_chat_id or None)
    return response
