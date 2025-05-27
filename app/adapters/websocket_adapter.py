from typing import Dict, Any
from app.core.ports.websocket_port import WebsocketPort
from app.controllers.websocket.websocket_server import manager

class WebsocketAdapter(WebsocketPort):
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        await manager.broadcast(message)
