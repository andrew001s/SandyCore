from app.core.ports.websocket_port import WebsocketPort
from app.services.avatar_events import build_speech_event, build_system_event


class ChatUseCase:
    def __init__(self, websocket_port: WebsocketPort):
        self.websocket_port = websocket_port
        self.chunk_message = []

    async def handle_message(
        self,
        username: str,
        message: str,
        response: str,
        *,
        voice_enabled: bool = True,
    ) -> None:
        self.chunk_message.append(f"{username}: {message}")
        await self.process_chunk(response, voice_enabled=voice_enabled)
        self.chunk_message.clear()

    async def process_chunk(self, response: str, *, voice_enabled: bool = True) -> None:
        source_message = self.chunk_message.copy()
        await self.websocket_port.broadcast_message(
            build_speech_event(
                response,
                priority=5,
                interrupt=False,
                scene="chat",
                metadata={
                    "source": "twitch_chat",
                    "messages": source_message,
                    "response": response,
                    "voice_enabled": voice_enabled,
                },
            )
        )

    async def notify_chat_connected(self, channel: str) -> None:
        await self.websocket_port.broadcast_message(
            build_system_event(
                "Chat de Twitch conectado y listo",
                metadata={
                    "source": "twitch_chat",
                    "channel": channel,
                },
            )
        )
