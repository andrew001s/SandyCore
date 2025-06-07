from datetime import datetime

from app.core.ports.websocket_port import WebsocketPort


class ChatUseCase:
    def __init__(self, websocket_port: WebsocketPort):
        self.websocket_port = websocket_port
        self.chunk_message = []

    async def handle_message(self, username: str, message: str, response: str) -> None:
        self.chunk_message.append(f"{username}: {message}")
        await self.process_chunk(response)
        self.chunk_message.clear()

    async def process_chunk(self, response: str) -> None:
        await self.websocket_port.broadcast_message(
            {
                "type": "twitch_response",
                "messages": self.chunk_message.copy(),
                "response": response,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def notify_chat_connected(self, channel: str) -> None:
        await self.websocket_port.broadcast_message(
            {
                "type": "chat_connected",
                "message": "Chat de Twitch conectado y listo",
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
            }
        )
