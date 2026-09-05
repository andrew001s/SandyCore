"""Fachada (Facade) para el módulo de servicios de YouTube.

Mantiene retrocompatibilidad total con adaptadores, routers y controladores existentes,
delegando responsabilidades en los módulos especializados (Arquitectura Limpia & SOLID):
- auth/: Autenticación OAuth 2.0 PKCE y cliente HTTP dedicado.
- events/: Modelos de dominio tipados, parser y manejador de eventos.
- lifecycle.py: Ciclo de vida y telemetría de servicios.
- monitor.py: Worker en segundo plano para detección de transmisiones y sondeo de chat.
- broadcaster.py: Operaciones de canal, transmisiones y envío de mensajes.
"""

from __future__ import annotations

from typing import Any

from app.services.youtube.auth.auth import (
    authenticate_youtube,
    build_authorization_url,
    complete_auth,
    delete_tokens as delete_youtube_saved_tokens,
    get_tokens as get_saved_youtube_tokens,
    revoke_token,
    save_tokens as save_youtube_tokens,
    start_auth,
)
from app.services.youtube.auth.client import YouTubeAPIClient
from app.services.youtube.broadcaster import (
    get_profile_users,
    get_stats,
    list_broadcasts,
    save_channel_context,
    send_chat_message,
    transition_broadcast,
    update_broadcast,
    _as_text,
    _extract_channel_payload,
    _extract_live_broadcast,
    _extract_live_chat_id,
)
from app.services.youtube.events.handler import YouTubeEventHandler
from app.services.youtube.events.parser import YouTubeEventParser
from app.services.youtube.lifecycle import (
    YouTubeLifecycleState,
    _get_state,
    _resolve_user_id,
    _utcnow,
    get_service_status,
    is_running,
    mark_activity,
    set_running,
    start_services,
    stop_services,
)
from app.services.youtube.monitor import LiveChatMonitor


async def get_tokens(user_id: str | None = None, bot: bool = False) -> dict[str, Any]:
    _ = bot
    resolved = _resolve_user_id(user_id)
    token = await get_saved_youtube_tokens(resolved)
    return {
        "provider": "google",
        "authenticated": bool(token and token.get("token")),
        "user_id": resolved,
        "expires_at": token.get("expires_at") if token else None,
        "scopes": token.get("scope") if token else [],
        "email": token.get("email") if token else None,
        "provider_account_id": token.get("provider_account_id") if token else None,
    }


async def logout(user_id: str | None = None) -> None:
    resolved = _resolve_user_id(user_id)
    tokens = await get_saved_youtube_tokens(resolved)
    if tokens:
        try:
            await revoke_token(tokens.get("refresh_token") or tokens.get("token") or "")
        except Exception as exc:
            print(f"[YOUTUBE AUTH] No se pudo revocar el token: {repr(exc)}")
    await delete_youtube_saved_tokens(resolved)


__all__ = [
    "LiveChatMonitor",
    "YouTubeAPIClient",
    "YouTubeEventHandler",
    "YouTubeEventParser",
    "YouTubeLifecycleState",
    "_as_text",
    "_extract_channel_payload",
    "_extract_live_broadcast",
    "_extract_live_chat_id",
    "_get_state",
    "_resolve_user_id",
    "_utcnow",
    "authenticate_youtube",
    "build_authorization_url",
    "complete_auth",
    "get_profile_users",
    "get_service_status",
    "get_stats",
    "get_tokens",
    "is_running",
    "list_broadcasts",
    "logout",
    "mark_activity",
    "save_channel_context",
    "send_chat_message",
    "set_running",
    "start_auth",
    "start_services",
    "stop_services",
    "transition_broadcast",
    "update_broadcast",
]
