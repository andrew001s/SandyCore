from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import httpx

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


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
        from app.services.youtube.auth.auth import refresh_access_token, save_tokens

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
        broadcast_status: str | None = "active",
        parts: str = "snippet,status,contentDetails",
        max_results: int = 10,
        mine: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": parts,
            "maxResults": str(max_results),
        }
        # En la API de YouTube v3, broadcastStatus y mine son mutuamente excluyentes.
        if broadcast_status:
            params["broadcastStatus"] = broadcast_status
        elif mine:
            params["mine"] = "true"
        else:
            params["broadcastStatus"] = "active"

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
                "part": "snippet,status,contentDetails",
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
