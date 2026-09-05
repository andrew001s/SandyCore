from __future__ import annotations

import asyncio
import collections
from typing import Any
import httpx

from app.services.client_settings import load_effective_settings, save_effective_settings
from app.services.youtube.auth.client import YouTubeAPIClient
from app.services.youtube.events.handler import YouTubeEventHandler
from app.services.youtube.events.models import YouTubeChatEnded
from app.services.youtube.events.parser import YouTubeEventParser


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


class LiveChatMonitor:
    """Worker en segundo plano para descubrimiento de directos y sondeo de chat de YouTube."""

    def __init__(self, user_id: str, client: YouTubeAPIClient, handler: YouTubeEventHandler):
        self.user_id = user_id
        self.client = client
        self.handler = handler
        self.live_chat_id: str | None = None
        self.broadcast_id: str | None = None
        self.next_page_token: str | None = None
        self.is_first_poll: bool = True
        self.seen_message_ids: collections.deque[str] = collections.deque(maxlen=2000)
        self._default_interval_seconds: float = 10.0

    async def save_context(
        self,
        channel: dict[str, Any],
        broadcast: dict[str, Any] | None = None,
        live_chat_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "youtube_channel_id": _as_text(channel.get("id")) or None,
            "youtube_channel_title": _as_text((channel.get("snippet") or {}).get("title")) or None,
        }
        if broadcast:
            payload["youtube_broadcast_id"] = _as_text(broadcast.get("id")) or None
        if live_chat_id:
            payload["youtube_live_chat_id"] = _as_text(live_chat_id) or None
        await save_effective_settings(payload, self.user_id)

    async def _discover_broadcast(self) -> tuple[dict[str, Any], dict[str, Any], str]:
        channel = await self.client.get_channel()
        if not channel:
            return {}, {}, ""

        broadcast: dict[str, Any] = {}
        live_chat_id = ""

        # 1. Buscar transmisiones actualmente activas
        try:
            active_broadcasts = await self.client.list_broadcasts(broadcast_status="active")
            broadcast = _extract_live_broadcast(active_broadcasts or {})
            live_chat_id = _extract_live_chat_id(broadcast)
        except Exception as exc:
            print(f"[YOUTUBE MONITOR] Error al listar transmisiones activas: {repr(exc)}")

        # 2. Si no hay directos activos, buscar directos programados/espera con chat abierto
        if not live_chat_id:
            try:
                upcoming_broadcasts = await self.client.list_broadcasts(broadcast_status="upcoming")
                broadcast = _extract_live_broadcast(upcoming_broadcasts or {})
                live_chat_id = _extract_live_chat_id(broadcast)
            except Exception as exc:
                print(f"[YOUTUBE MONITOR] Error al listar transmisiones programadas: {repr(exc)}")

        # 3. Fallback a configuración guardada previamente si aplica
        if not live_chat_id:
            settings = await load_effective_settings(self.user_id)
            live_chat_id = _as_text(settings.get("youtube_live_chat_id"))

        if live_chat_id:
            await self.save_context(channel, broadcast, live_chat_id)

        return channel, broadcast, live_chat_id

    async def run(self) -> None:
        from app.services.youtube.lifecycle import _get_state, mark_activity

        state = await _get_state(self.user_id)
        print(f"[YOUTUBE MONITOR] Iniciando monitor de chat de YouTube para {self.user_id}")

        while state.running and state.armed:
            # 1. Si no tenemos live_chat_id enlazado, intentamos descubrirlo
            if not self.live_chat_id:
                try:
                    channel, broadcast, found_chat_id = await self._discover_broadcast()
                    if found_chat_id:
                        self.live_chat_id = found_chat_id
                        self.broadcast_id = broadcast.get("id") or self.broadcast_id
                        self.next_page_token = None
                        self.is_first_poll = True
                        state.live_chat_id = found_chat_id
                        state.broadcast_id = self.broadcast_id
                        state.last_known_live = True
                        print(f"[YOUTUBE MONITOR] Directo detectado para {self.user_id}, chat: {found_chat_id}")
                    else:
                        state.last_known_live = False
                        # Esperar antes de volver a verificar transmisiones en vivo
                        await asyncio.sleep(15.0)
                        continue
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    print(f"[YOUTUBE MONITOR] Esperando directo de YouTube ({self.user_id}): {repr(exc)}")
                    await asyncio.sleep(15.0)
                    continue

            # 2. Sondeo de mensajes del chat en vivo
            try:
                response = await self.client.get_live_chat_messages(
                    self.live_chat_id,
                    page_token=self.next_page_token,
                    max_results=200,
                )

                items = response.get("items") or []
                self.next_page_token = response.get("nextPageToken") or self.next_page_token
                polling_interval_ms = int(
                    response.get("pollingIntervalMillis") or (self._default_interval_seconds * 1000)
                )

                if self.is_first_poll:
                    # En la primera llamada se registran los mensajes existentes para no responder
                    # a mensajes históricos previos al encendido del bot
                    for item in items:
                        item_id = _as_text(item.get("id"))
                        if item_id:
                            self.seen_message_ids.append(item_id)
                    self.is_first_poll = False
                else:
                    # Procesar únicamente los mensajes nuevos que van llegando
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        item_id = _as_text(item.get("id"))
                        if item_id and item_id in self.seen_message_ids:
                            continue
                        if item_id:
                            self.seen_message_ids.append(item_id)

                        event = YouTubeEventParser.parse(item)
                        if event is not None:
                            if isinstance(event, YouTubeChatEnded):
                                print(f"[YOUTUBE MONITOR] La transmisión finalizó para {self.user_id}")
                                self.live_chat_id = None
                                self.next_page_token = None
                                self.is_first_poll = True
                                state.live_chat_id = None
                                state.last_known_live = False
                                break

                            await self.handler.handle_event(event, self.live_chat_id)
                            await mark_activity(self.user_id)

                sleep_seconds = max(1.0, polling_interval_ms / 1000.0)
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except httpx.HTTPStatusError as exc:
                is_chat_ended = (
                    exc.response.status_code == 404
                    or "liveChatEnded" in exc.response.text
                    or "no longer live" in exc.response.text
                )
                if is_chat_ended:
                    print(f"[YOUTUBE MONITOR] Chat de YouTube finalizado o no disponible ({exc.response.status_code}). Reseteando enlace.")
                    self.live_chat_id = None
                    self.next_page_token = None
                    self.is_first_poll = True
                    state.live_chat_id = None
                    state.last_known_live = False
                    await asyncio.sleep(15.0)
                elif exc.response.status_code in (401, 403):
                    print(f"[YOUTUBE MONITOR] Error {exc.response.status_code} en API de YouTube: {exc.response.text}")
                    await asyncio.sleep(60.0)
                else:
                    print(f"[YOUTUBE MONITOR] Error HTTP al consultar chat: {repr(exc)}")
                    await asyncio.sleep(self._default_interval_seconds)

            except Exception as exc:
                print(f"[YOUTUBE MONITOR] Error inesperado en monitor: {repr(exc)}")
                await asyncio.sleep(self._default_interval_seconds)

        print(f"[YOUTUBE MONITOR] Monitor detenido para {self.user_id}")
