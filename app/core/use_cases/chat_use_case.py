import re

from app.core.ports.websocket_port import WebsocketPort
from app.services.avatar_events import build_speech_event, build_system_event
from app.services.client_settings import load_effective_settings
from app.domain.automatic_reactions import filter_reaction_decision


_REACTION_MARKER = re.compile(
    r"\s*\[\[REACTION:(none|happy|sad|angry|surprised|excited|sleepy|thinking|confused|shy)\]\]\s*$",
    re.IGNORECASE,
)


def strip_reaction_marker(response: str) -> tuple[str, bool | None, str | None]:
    match = _REACTION_MARKER.search(response)
    if not match:
        return response, None, None

    emotion = match.group(1).lower()
    clean_response = response[: match.start()].rstrip()
    if emotion == "none":
        return clean_response, False, None
    return clean_response, True, emotion


class ChatUseCase:
    """Sin estado propio: el chunk viaja como argumento.

    Guardarlo en `self` hacía que dos chats concurrentes se intercalaran y el
    evento de un streamer saliera con los mensajes del otro.
    """

    def __init__(self, websocket_port: WebsocketPort):
        self.websocket_port = websocket_port

    async def handle_message(
        self,
        username: str,
        message: str,
        response: str,
        *,
        user_id: str,
        voice_enabled: bool = True,
    ) -> None:
        await self.process_chunk(
            response,
            messages=[f"{username}: {message}"],
            user_id=user_id,
            voice_enabled=voice_enabled,
        )

    async def process_chunk(
        self,
        response: str,
        *,
        messages: list[str],
        user_id: str,
        voice_enabled: bool = True,
    ) -> None:
        clean_response, reaction, emotion = strip_reaction_marker(response)
        settings = await load_effective_settings(user_id)
        reaction, emotion = filter_reaction_decision(reaction, emotion, settings)
        print(
            f"[CHAT REACTION] user_id={user_id} "
            f"decision={reaction!r} emotion={emotion!r}"
        )
        event = build_speech_event(
            clean_response,
            emotion=emotion or "neutral",
            priority=5,
            interrupt=False,
            scene="chat",
            metadata={
                "source": "twitch_chat",
                "user_id": user_id,
                "messages": list(messages),
                "response": clean_response,
                "voice_enabled": voice_enabled,
            },
        )
        event["reaction"] = reaction
        if not reaction:
            event["emotion"] = None
            event["expression"] = None
        await self.websocket_port.broadcast_message(
            event,
            user_id,
        )

    async def notify_chat_connected(self, channel: str, user_id: str) -> None:
        await self.websocket_port.broadcast_message(
            build_system_event(
                "Chat de Twitch conectado y listo",
                metadata={
                    "source": "twitch_chat",
                    "user_id": user_id,
                    "channel": channel,
                },
            ),
            user_id,
        )
