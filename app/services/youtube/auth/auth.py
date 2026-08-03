from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import config
from app.core.runtime import get_active_user_id
from app.services.storage.supabase_store import (
    delete_youtube_tokens,
    get_youtube_tokens,
    save_youtube_tokens,
)

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
YOUTUBE_STATE_TTL_SECONDS = 15 * 60
DEFAULT_REDIRECT_URI = "/youtube/auth/callback"


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return owner_id


def _now() -> int:
    return int(time.time())


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _sha256(text: str) -> str:
    return _urlsafe_b64encode(hashlib.sha256(text.encode("utf-8")).digest())


def _normalize_scope(scope: Any) -> list[str]:
    if scope is None:
        return []
    if isinstance(scope, list):
        return [str(item).strip() for item in scope if str(item).strip()]
    if isinstance(scope, str):
        return [item.strip() for item in scope.split(" ") if item.strip()]
    return [str(scope).strip()]


@dataclass(slots=True)
class OAuthState:
    user_id: str
    code_verifier: str
    created_at: int
    redirect_uri: str


_oauth_states: dict[str, OAuthState] = {}


def _cleanup_state_cache() -> None:
    expired = [
        state
        for state, payload in _oauth_states.items()
        if _now() - payload.created_at > YOUTUBE_STATE_TTL_SECONDS
    ]
    for state in expired:
        _oauth_states.pop(state, None)


def _build_redirect_uri(redirect_uri: str | None = None) -> str:
    resolved = (redirect_uri or config.YOUTUBE_REDIRECT_URI or DEFAULT_REDIRECT_URI).strip()
    if not resolved:
        raise Exception("Falta YOUTUBE_REDIRECT_URI en la configuración")
    return resolved


def _require_client_config() -> tuple[str, str]:
    client_id = config.YOUTUBE_CLIENT_ID
    client_secret = config.YOUTUBE_CLIENT_SECRET
    if not client_id or not client_secret:
        raise Exception("Faltan YOUTUBE_CLIENT_ID o YOUTUBE_CLIENT_SECRET en la configuración")
    return client_id, client_secret


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = _sha256(verifier)
    return verifier, challenge


def build_authorization_url(
    user_id: str | None = None,
    *,
    redirect_uri: str | None = None,
    scopes: list[str] | None = None,
) -> dict[str, str]:
    owner_id = _resolve_user_id(user_id)
    client_id, _ = _require_client_config()
    resolved_redirect_uri = _build_redirect_uri(redirect_uri)
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = OAuthState(
        user_id=owner_id,
        code_verifier=verifier,
        created_at=_now(),
        redirect_uri=resolved_redirect_uri,
    )
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": resolved_redirect_uri,
        "state": state,
        "scope": " ".join(scopes or YOUTUBE_SCOPES),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return {
        "authorization_url": f"{YOUTUBE_AUTH_BASE_URL}?{urlencode(query)}",
        "state": state,
        "redirect_uri": resolved_redirect_uri,
        "scopes": query["scope"],
    }


def _consume_state(state: str) -> OAuthState:
    _cleanup_state_cache()
    payload = _oauth_states.pop(state, None)
    if payload is None:
        raise Exception("El estado de OAuth de YouTube no es válido o expiró")
    return payload


async def exchange_authorization_code(
    code: str,
    state: str,
    *,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    state_payload = _consume_state(state)
    client_id, client_secret = _require_client_config()
    resolved_redirect_uri = _build_redirect_uri(redirect_uri or state_payload.redirect_uri)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": resolved_redirect_uri,
        "code_verifier": state_payload.code_verifier,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            YOUTUBE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code != 200:
        raise Exception(f"No se pudo completar el OAuth de YouTube: {response.status_code} {response.text}")
    payload = response.json()
    return {
        "user_id": state_payload.user_id,
        "redirect_uri": resolved_redirect_uri,
        "token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "expires_at": _now() + int(payload.get("expires_in") or 0),
        "scope": _normalize_scope(payload.get("scope")),
        "token_type": payload.get("token_type"),
        "id_token": payload.get("id_token"),
    }


async def refresh_access_token(user_id: str, refresh_token: str) -> dict[str, Any]:
    client_id, client_secret = _require_client_config()
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            YOUTUBE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code != 200:
        raise Exception(f"No se pudo refrescar el token de YouTube: {response.status_code} {response.text}")
    payload = response.json()
    return {
        "user_id": user_id,
        "token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token") or refresh_token,
        "expires_in": payload.get("expires_in"),
        "expires_at": _now() + int(payload.get("expires_in") or 0),
        "scope": _normalize_scope(payload.get("scope")),
        "token_type": payload.get("token_type"),
    }


async def revoke_token(token: str) -> None:
    if not token:
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            YOUTUBE_REVOKE_URL,
            params={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code not in (200, 204):
        raise Exception(f"No se pudo revocar el token de YouTube: {response.status_code} {response.text}")


async def save_tokens(
    user_id: str | None = None,
    token: str | None = None,
    refresh_token: str | None = None,
    *,
    expires_at: int | None = None,
    scope: str | list[str] | None = None,
    token_type: str | None = None,
    provider_account_id: str | None = None,
    email: str | None = None,
) -> None:
    owner_id = _resolve_user_id(user_id)
    if not token or not refresh_token:
        raise Exception("No se recibieron tokens válidos de YouTube")
    await save_youtube_tokens(
        owner_id,
        token,
        refresh_token,
        expires_at=expires_at,
        scope=scope,
        token_type=token_type,
        provider_account_id=provider_account_id,
        email=email,
    )


async def get_tokens(user_id: str | None = None) -> dict[str, Any] | None:
    owner_id = _resolve_user_id(user_id)
    return await get_youtube_tokens(owner_id)


async def delete_tokens(user_id: str | None = None) -> None:
    owner_id = _resolve_user_id(user_id)
    await delete_youtube_tokens(owner_id)


async def authenticate_youtube(user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    tokens = await get_tokens(owner_id)
    if not tokens:
        raise Exception("No existen tokens de YouTube guardados para este usuario")

    access_token = tokens.get("token")
    refresh_token = tokens.get("refresh_token")
    expires_at = tokens.get("expires_at")

    if expires_at and int(expires_at) <= _now() and refresh_token:
        refreshed = await refresh_access_token(owner_id, refresh_token)
        access_token = refreshed["token"]
        refresh_token = refreshed["refresh_token"]
        await save_tokens(
            owner_id,
            access_token,
            refresh_token,
            expires_at=refreshed.get("expires_at"),
            scope=refreshed.get("scope"),
            token_type=refreshed.get("token_type"),
            provider_account_id=tokens.get("provider_account_id"),
            email=tokens.get("email"),
        )

    if not access_token:
        raise Exception("No existen tokens de YouTube guardados para este usuario")

    return YouTubeAPIClient(owner_id, access_token, refresh_token=refresh_token)


@dataclass
class YouTubeAPIClient:
    user_id: str
    access_token: str
    refresh_token: str | None = None

    @property
    def api_base_url(self) -> str:
        return YOUTUBE_API_BASE_URL.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    async def _refresh_if_needed(self) -> None:
        if not self.refresh_token:
            raise Exception("El token de YouTube expiró y no hay refresh token disponible")
        refreshed = await refresh_access_token(self.user_id, self.refresh_token)
        self.access_token = refreshed["token"]
        self.refresh_token = refreshed["refresh_token"]
        await save_tokens(
            self.user_id,
            self.access_token,
            self.refresh_token,
            expires_at=refreshed.get("expires_at"),
            scope=refreshed.get("scope"),
            token_type=refreshed.get("token_type"),
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | list[tuple[str, str]] | None = None,
        json_body: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> Any:
        url = f"{self.api_base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._headers(),
            )

        if response.status_code in (401, 403) and retry:
            await self._refresh_if_needed()
            return await self.request_json(
                method,
                path,
                params=params,
                json_body=json_body,
                retry=False,
            )

        response.raise_for_status()
        if not response.content:
            return None
        try:
            return response.json()
        except Exception:
            return response.text

    async def get_channel(
        self,
        *,
        parts: str = "snippet,statistics,contentDetails,brandingSettings",
    ) -> dict[str, Any]:
        response = await self.request_json(
            "GET",
            "/channels",
            params={"part": parts, "mine": "true", "maxResults": "1"},
        )
        items = (response or {}).get("items") or []
        return items[0] if items else {}

    async def list_broadcasts(
        self,
        *,
        broadcast_status: str = "active",
        parts: str = "snippet,status,contentDetails,statistics",
        max_results: int = 10,
    ) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            "/liveBroadcasts",
            params={
                "part": parts,
                "mine": "true",
                "broadcastStatus": broadcast_status,
                "maxResults": str(max_results),
            },
        )

    async def get_broadcast(self, broadcast_id: str) -> dict[str, Any]:
        response = await self.request_json(
            "GET",
            "/liveBroadcasts",
            params={
                "part": "snippet,status,contentDetails,statistics",
                "id": broadcast_id,
                "maxResults": "1",
            },
        )
        items = (response or {}).get("items") or []
        return items[0] if items else {}

    async def get_live_chat_messages(
        self,
        live_chat_id: str,
        *,
        page_token: str | None = None,
        max_results: int = 200,
        profile_image_size: int = 88,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "liveChatId": live_chat_id,
            "part": "id,snippet,authorDetails",
            "maxResults": str(max_results),
            "profileImageSize": str(profile_image_size),
        }
        if page_token:
            params["pageToken"] = page_token
        return await self.request_json("GET", "/liveChat/messages", params=params)

    async def send_chat_message(self, live_chat_id: str, message: str) -> Any:
        return await self.request_json(
            "POST",
            "/liveChat/messages",
            params={"part": "snippet"},
            json_body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": message,
                    },
                }
            },
        )

    async def delete_chat_message(self, message_id: str) -> Any:
        return await self.request_json(
            "DELETE",
            "/liveChat/messages",
            params={"id": message_id},
        )

    async def update_live_broadcast(
        self, broadcast_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        current = await self.get_broadcast(broadcast_id)
        if not current:
            raise Exception("No se encontró la transmisión de YouTube solicitada")

        current_snippet = current.get("snippet") or {}
        current_status = current.get("status") or {}
        current_content_details = current.get("contentDetails") or {}
        current_monitor_stream = current_content_details.get("monitorStream") or {}

        snippet = dict(current_snippet)
        status = dict(current_status)
        content_details = dict(current_content_details)
        content_details["monitorStream"] = dict(current_monitor_stream)

        for key in ("title", "description", "scheduledStartTime", "scheduledEndTime"):
            if key in payload and payload[key] is not None:
                snippet[key] = payload[key]

        if payload.get("privacyStatus"):
            status["privacyStatus"] = payload["privacyStatus"]

        if payload.get("enableMonitorStream") is not None:
            content_details["monitorStream"]["enableMonitorStream"] = bool(
                payload["enableMonitorStream"]
            )
        if payload.get("broadcastStreamDelayMs") is not None:
            content_details["monitorStream"]["broadcastStreamDelayMs"] = int(
                payload["broadcastStreamDelayMs"]
            )

        body = {
            "id": broadcast_id,
            "snippet": snippet,
            "status": status,
            "contentDetails": content_details,
        }
        return await self.request_json(
            "PUT",
            "/liveBroadcasts",
            params={"part": "snippet,status,contentDetails"},
            json_body=body,
        )

    async def transition_live_broadcast(
        self, broadcast_id: str, status: str
    ) -> dict[str, Any]:
        return await self.request_json(
            "POST",
            "/liveBroadcasts/transition",
            params={
                "part": "snippet,status,contentDetails",
                "broadcastStatus": status,
                "id": broadcast_id,
            },
        )

    async def get_stats(self) -> dict[str, Any]:
        channel = await self.get_channel(parts="snippet,statistics,contentDetails")
        statistics = channel.get("statistics") or {}
        snippet = channel.get("snippet") or {}
        content_details = channel.get("contentDetails") or {}
        return {
            "channelId": channel.get("id"),
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "customUrl": snippet.get("customUrl"),
            "thumbnail": (
                (snippet.get("thumbnails") or {}).get("high")
                or (snippet.get("thumbnails") or {}).get("default")
                or {}
            ).get("url"),
            "uploadsPlaylistId": (content_details.get("relatedPlaylists") or {}).get(
                "uploads"
            ),
            "subscriberCount": statistics.get("subscriberCount"),
            "viewCount": statistics.get("viewCount"),
            "videoCount": statistics.get("videoCount"),
        }
