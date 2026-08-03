from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import config
from app.core.runtime import get_active_user_id

YOUTUBE_OAUTH_PROVIDER = "google"
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
CLERK_API_BASE_URL = "https://api.clerk.com/v1"
YOUTUBE_SCOPES = {
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
}


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return owner_id


def _extract_token_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _pick_google_access_token(tokens: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tokens:
        return None

    def _score(item: dict[str, Any]) -> tuple[int, int]:
        scopes = {str(scope).strip() for scope in item.get("scopes") or []}
        full_scope_match = bool(scopes & {"https://www.googleapis.com/auth/youtube"})
        force_ssl_match = bool(scopes & {"https://www.googleapis.com/auth/youtube.force-ssl"})
        readonly_match = bool(scopes & {"https://www.googleapis.com/auth/youtube.readonly"})
        yt_analytics_match = bool(scopes & {"https://www.googleapis.com/auth/yt-analytics.readonly"})
        return (
            1 if full_scope_match or force_ssl_match else 0,
            1 if readonly_match or yt_analytics_match else 0,
        )

    sorted_tokens = sorted(tokens, key=_score, reverse=True)
    return sorted_tokens[0] if sorted_tokens else None


async def get_google_oauth_token(user_id: str | None = None) -> dict[str, Any]:
    owner_id = _resolve_user_id(user_id)
    if not config.CLERK_SECRET_KEY:
        raise Exception("Falta CLERK_SECRET_KEY para consultar los tokens OAuth de Clerk")

    url = f"{CLERK_API_BASE_URL}/users/{owner_id}/oauth_access_tokens/{YOUTUBE_OAUTH_PROVIDER}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {config.CLERK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()

    tokens = _extract_token_payload(payload)
    token = _pick_google_access_token(tokens)
    if not token or not token.get("token"):
        raise Exception("No existen tokens de Google guardados para este usuario")
    return token


async def get_google_access_token(user_id: str | None = None) -> str:
    token = await get_google_oauth_token(user_id)
    return str(token["token"])


@dataclass
class YouTubeAPIClient:
    user_id: str
    access_token: str

    @property
    def api_base_url(self) -> str:
        return YOUTUBE_API_BASE_URL.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

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
            refreshed = await get_google_access_token(self.user_id)
            self.access_token = refreshed
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
        params: dict[str, Any] = {
            "part": parts,
            "mine": "true",
            "broadcastStatus": broadcast_status,
            "maxResults": str(max_results),
        }
        return await self.request_json(
            "GET",
            "/liveBroadcasts",
            params=params,
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

    async def update_live_broadcast(self, broadcast_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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
            content_details["monitorStream"]["enableMonitorStream"] = bool(payload["enableMonitorStream"])
        if payload.get("broadcastStreamDelayMs") is not None:
            content_details["monitorStream"]["broadcastStreamDelayMs"] = int(payload["broadcastStreamDelayMs"])

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

    async def transition_live_broadcast(self, broadcast_id: str, status: str) -> dict[str, Any]:
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
            "uploadsPlaylistId": (content_details.get("relatedPlaylists") or {}).get("uploads"),
            "subscriberCount": statistics.get("subscriberCount"),
            "viewCount": statistics.get("viewCount"),
            "videoCount": statistics.get("videoCount"),
        }


async def authenticate_youtube(user_id: str | None = None) -> YouTubeAPIClient:
    owner_id = _resolve_user_id(user_id)
    access_token = await get_google_access_token(owner_id)
    return YouTubeAPIClient(owner_id, access_token)
