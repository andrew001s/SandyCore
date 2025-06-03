from datetime import datetime

from app.core.ports.websocket_port import WebsocketPort


class EventSubUseCase:
    def __init__(self, websocket_port: WebsocketPort):
        self.websocket_port = websocket_port

    async def handle_events(self, message: str, response: str) -> None:
        await self.websocket_port.broadcast_message(
            {
                "type": "twitch_response",
                "messages": message,
                "response": response,
                "timestamp": datetime.now().isoformat(),
            }
        )
