from app.core.ports.websocket_port import WebsocketPort
from app.services.avatar_events import build_speech_event, build_system_event


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
        await self.websocket_port.broadcast_message(
            build_speech_event(
                response,
                priority=5,
                interrupt=False,
                scene="chat",
                metadata={
                    "source": "twitch_chat",
                    "user_id": user_id,
                    "messages": list(messages),
                    "response": response,
                    "voice_enabled": voice_enabled,
                },
            ),
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
