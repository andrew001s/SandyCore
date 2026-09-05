from __future__ import annotations

import collections
from typing import Any
import httpx
from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.client_settings import load_effective_settings, resolve_feature_flags
from app.services.gemini import (
    response_gemini_events,
    response_gemini_rewards,
    response_sandy,
    should_delete_message,
    try_local_task,
)
from app.services.moderator import check_banned_words
from app.services.storage.supabase_store import get_custom_reward_by_id_or_title
from app.services.youtube.auth.client import YouTubeAPIClient
from app.services.youtube.events.models import (
    YouTubeChatEnded,
    YouTubeEvent,
    YouTubeGiftMembershipReceived,
    YouTubeMemberMilestone,
    YouTubeMembershipGifting,
    YouTubeNewSponsor,
    YouTubeSuperChat,
    YouTubeSuperSticker,
    YouTubeTextMessage,
    YouTubeUserBanned,
)

DEFAULT_BOTS = {"nightbot", "streamelements", "streamlabs", "moobot"}


class YouTubeEventHandler:
    """Manejador y despachador de eventos de YouTube (SOLID: Strategy & Dispatcher)."""

    def __init__(
        self,
        user_id: str,
        client: YouTubeAPIClient,
        websocket_adapter: WebsocketAdapter | None = None,
        event_use_case: EventSubUseCase | None = None,
    ):
        self.user_id = user_id
        self.client = client
        self.websocket_adapter = websocket_adapter or WebsocketAdapter()
        self.event_use_case = event_use_case or EventSubUseCase(self.websocket_adapter)
        # Bounded cache para IDs de mensajes enviados por el bot y no auto-responderse
        self.sent_message_ids: collections.deque[str] = collections.deque(maxlen=500)

    def record_sent_message(self, message_id: str | None) -> None:
        if message_id:
            self.sent_message_ids.append(str(message_id))

    async def _resolve_bots(self, settings: dict[str, Any]) -> set[str]:
        bots = set(DEFAULT_BOTS)
        bot_account = str(settings.get("youtube_bot_account") or "").strip().lower()
        if bot_account:
            bots.add(bot_account)
        return bots

    async def handle_event(self, event: YouTubeEvent, live_chat_id: str) -> None:
        if isinstance(event, YouTubeTextMessage):
            await self._handle_text_message(event, live_chat_id)
        elif isinstance(event, YouTubeSuperChat):
            await self._handle_super_chat(event)
        elif isinstance(event, YouTubeSuperSticker):
            await self._handle_super_sticker(event)
        elif isinstance(event, YouTubeNewSponsor):
            await self._handle_new_sponsor(event)
        elif isinstance(event, YouTubeMemberMilestone):
            await self._handle_member_milestone(event)
        elif isinstance(event, YouTubeMembershipGifting):
            await self._handle_membership_gifting(event)
        elif isinstance(event, YouTubeGiftMembershipReceived):
            await self._handle_gift_received(event)
        elif isinstance(event, YouTubeUserBanned):
            await self._handle_user_banned(event)
        elif isinstance(event, YouTubeChatEnded):
            print(f"[YOUTUBE EVENT] Chat finalizado para {self.user_id}")

    async def _handle_text_message(self, event: YouTubeTextMessage, live_chat_id: str) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        bots = await self._resolve_bots(settings)

        author_name = event.author.display_name
        # Ignorar si es un bot configurado o si es un mensaje enviado por Sandy
        if author_name.lower() in bots or event.event_id in self.sent_message_ids:
            return

        print(f"[YOUTUBE CHAT] {author_name}: {event.text}")

        # Moderación de palabras prohibidas
        if feature_flags.get("moderation", True):
            is_banned = await check_banned_words(event.text, self.user_id)
            if is_banned:
                print(
                    f"[YOUTUBE MODERACION] Palabra prohibida detectada en mensaje de {author_name}: "
                    f"{event.text!r}. Consultando a la IA..."
                )
                if await should_delete_message(event.text, self.user_id):
                    print(f"[YOUTUBE MODERACION] IA confirmó infracción para {author_name}. Eliminando mensaje...")
                    try:
                        if event.event_id:
                            await self.client.delete_chat_message(event.event_id)
                            print(f"[YOUTUBE MODERACION] Mensaje {event.event_id} eliminado exitosamente de YouTube")
                    except Exception as exc:
                        print(f"[YOUTUBE MODERACION] No se pudo borrar el mensaje: {repr(exc)}")

                    warning_message = (
                        f"@{author_name} tu mensaje fue eliminado por moderación. "
                        "Evita usar palabras prohibidas."
                    )
                    try:
                        res = await self.client.send_chat_message(live_chat_id, warning_message)
                        if isinstance(res, dict) and res.get("id"):
                            self.record_sent_message(res.get("id"))
                    except Exception as exc:
                        print(f"[YOUTUBE MODERACION] No se pudo enviar advertencia: {repr(exc)}")
                    return
                else:
                    print(f"[YOUTUBE MODERACION] IA determinó que el mensaje es inocuo en contexto: {event.text!r}")
            else:
                print(f"[YOUTUBE MODERACION] Sin coincidencias en diccionario para: {event.text!r}")
        else:
            print(f"[YOUTUBE MODERACION] Moderación desactivada en la configuración")

        if not feature_flags.get("chat_replies", True):
            print(f"[YOUTUBE CHAT] chat_replies desactivado para {self.user_id}")
            return

        full_message = f"{author_name}: {event.text}".strip()
        voice_enabled = bool(feature_flags.get("voice_replies", True))

        # Solo si las respuestas por voz están activadas se delega en el navegador para hablar
        if voice_enabled:
            if await try_local_task("chat", full_message, "vtuber", self.user_id):
                return

        try:
            response = await response_sandy(full_message, self.user_id)
        except Exception as exc:
            print(f"[YOUTUBE CHAT] Error al generar respuesta: {repr(exc)}")
            return

        # Si las respuestas por voz están activadas, mandamos el evento de voz al frontend
        if voice_enabled:
            await self.event_use_case.handle_events(
                "speech",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        else:
            # Respuestas por voz INACTIVAS: enviar directamente en texto al chat de YouTube
            print(f"[YOUTUBE CHAT] Respuestas por voz inactivas. Enviando respuesta en texto al chat: {response!r}")
            try:
                sent = await self.client.send_chat_message(live_chat_id, response)
                if isinstance(sent, dict) and sent.get("id"):
                    self.record_sent_message(sent.get("id"))
                    print(f"[YOUTUBE CHAT] Mensaje enviado al chat exitosamente (ID: {sent.get('id')})")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404 or "liveChatEnded" in exc.response.text:
                    print(f"[YOUTUBE CHAT] El chat de YouTube finalizó: {exc.response.text}")
                    from app.services.youtube.lifecycle import _get_state

                    state = await _get_state(self.user_id)
                    state.live_chat_id = None
                    state.last_known_live = False
                    if state.monitor:
                        state.monitor.live_chat_id = None
                        state.monitor.next_page_token = None
                        state.monitor.is_first_poll = True
                else:
                    print(f"[YOUTUBE CHAT] Error HTTP al responder en el chat: {repr(exc)}")
            except Exception as exc:
                print(f"[YOUTUBE CHAT] No se pudo responder en el chat: {repr(exc)}")


    async def _handle_super_chat(self, event: YouTubeSuperChat) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("rewards", True):
            return

        full_message = f"Super Chat de {event.author.display_name} ({event.amount}): {event.comment}".strip()
        print(f"[YOUTUBE REWARD] {full_message}")

        # Soporte de recompensas personalizadas de Supabase
        db_reward = await get_custom_reward_by_id_or_title(
            self.user_id, "youtube", "superchat", "superchat"
        )
        custom_prompt = db_reward.get("prompt") if db_reward and db_reward.get("enabled") else None

        if await try_local_task("reaction", full_message, "rewards", self.user_id):
            return

        try:
            response = await response_gemini_rewards(full_message, self.user_id, custom_prompt)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        except Exception as exc:
            print(f"[YOUTUBE REWARD] Error al reaccionar a Super Chat: {repr(exc)}")

    async def _handle_super_sticker(self, event: YouTubeSuperSticker) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("rewards", True):
            return

        full_message = f"Super Sticker de {event.author.display_name} ({event.amount}): {event.alt_text}".strip()
        print(f"[YOUTUBE REWARD] {full_message}")

        db_reward = await get_custom_reward_by_id_or_title(
            self.user_id, "youtube", "supersticker", "supersticker"
        )
        custom_prompt = db_reward.get("prompt") if db_reward and db_reward.get("enabled") else None

        if await try_local_task("reaction", full_message, "rewards", self.user_id):
            return

        try:
            response = await response_gemini_rewards(full_message, self.user_id, custom_prompt)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        except Exception as exc:
            print(f"[YOUTUBE REWARD] Error al reaccionar a Super Sticker: {repr(exc)}")

    async def _handle_new_sponsor(self, event: YouTubeNewSponsor) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("events", True):
            return

        action = "ha subido de nivel su membresía a" if event.is_upgrade else "se ha unido como nuevo miembro en"
        full_message = f"{event.author.display_name} {action} {event.level_name}"
        print(f"[YOUTUBE EVENT] {full_message}")

        if await try_local_task("reaction", full_message, "events", self.user_id):
            return

        try:
            response = await response_gemini_events(full_message, self.user_id)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        except Exception as exc:
            print(f"[YOUTUBE EVENT] Error al reaccionar a nuevo patrocinador: {repr(exc)}")

    async def _handle_member_milestone(self, event: YouTubeMemberMilestone) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("events", True):
            return

        comment_part = f": {event.comment}" if event.comment else ""
        full_message = (
            f"Renovación de membresía de {event.author.display_name} "
            f"({event.months} meses, nivel {event.level_name}){comment_part}"
        ).strip()
        print(f"[YOUTUBE EVENT] {full_message}")

        if await try_local_task("reaction", full_message, "events", self.user_id):
            return

        try:
            response = await response_gemini_events(full_message, self.user_id)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        except Exception as exc:
            print(f"[YOUTUBE EVENT] Error al reaccionar a hito de membresía: {repr(exc)}")

    async def _handle_membership_gifting(self, event: YouTubeMembershipGifting) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("events", True):
            return

        full_message = f"{event.author.display_name} ha regalado {event.gift_count} membresías de nivel {event.level_name}!"
        print(f"[YOUTUBE EVENT] {full_message}")

        if await try_local_task("reaction", full_message, "events", self.user_id):
            return

        try:
            response = await response_gemini_events(full_message, self.user_id)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=True,
            )
        except Exception as exc:
            print(f"[YOUTUBE EVENT] Error al reaccionar a regalo de membresías: {repr(exc)}")

    async def _handle_gift_received(self, event: YouTubeGiftMembershipReceived) -> None:
        print(f"[YOUTUBE EVENT] {event.author.display_name} recibió una membresía regalada ({event.level_name})")

    async def _handle_user_banned(self, event: YouTubeUserBanned) -> None:
        settings = await load_effective_settings(self.user_id)
        feature_flags = resolve_feature_flags(settings)
        if not feature_flags.get("events", True):
            return

        full_message = f"Usuario baneado del chat de YouTube: {event.banned_user_name} ({event.ban_type})"
        print(f"[YOUTUBE EVENT] {full_message}")
        try:
            response = await response_gemini_events(full_message, self.user_id)
            await self.event_use_case.handle_events(
                "reaction",
                full_message,
                response,
                user_id=self.user_id,
                voice_enabled=False,
            )
        except Exception as exc:
            print(f"[YOUTUBE EVENT] Error al reaccionar a usuario baneado: {repr(exc)}")
