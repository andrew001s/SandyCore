from typing import Any, Dict

from app.controllers.websocket.websocket_server import manager
from app.core.ports.websocket_port import WebsocketPort


class WebsocketAdapter(WebsocketPort):
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        await manager.broadcast(message)
