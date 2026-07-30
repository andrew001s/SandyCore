import asyncio
import json
from typing import Any, Dict, List

from fastapi import WebSocket, WebSocketDisconnect

from app.models.websocket_models import (
    ChatMessage,
    ConnectionMessage,
    ErrorMessage,
    NotificationMessage,
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.active_streams: List[asyncio.Queue[Dict[str, Any]]] = []
        self.connection_count = 0

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_count += 1
        return self.connection_count

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def connect_stream(self, user_id: str) -> asyncio.Queue[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self.active_streams.append(queue)
        return queue

    async def disconnect_stream(self, queue: asyncio.Queue[Dict[str, Any]]):
        if queue in self.active_streams:
            self.active_streams.remove(queue)

    async def broadcast(self, message: Dict[str, Any]):
        stale_connections: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)

        for connection in stale_connections:
            await self.disconnect(connection)

        for queue in list(self.active_streams):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    _ = queue.get_nowait()
                    queue.put_nowait(message)
                except Exception:
                    continue

    async def send_personal_message(
        self, message: Dict[str, Any], websocket: WebSocket
    ):
        await websocket.send_json(message)


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket):
    client_id = await manager.connect(websocket)
    try:
        # Enviar mensaje de bienvenida usando el modelo
        welcome_message = ConnectionMessage(
            type="connection_established",
            client_id=client_id,
            message="✅ Conectado al servidor WebSocket",
        )
        await manager.send_personal_message(welcome_message.dict(), websocket)

        while True:
            try:
                # Recibir datos y convertir según el tipo de mensaje
                data = await websocket.receive_text()
                message_data = json.loads(data)

                message_type = message_data.get("type", "chat")

                if message_type == "chat":
                    message = ChatMessage(
                        type=message_type,
                        client_id=client_id,
                        messages=message_data.get("messages", []),
                        response=message_data.get("response", ""),
                    )
                elif message_type == "notification":
                    message = NotificationMessage(
                        type=message_type,
                        client_id=client_id,
                        event_type=message_data.get("event_type", ""),
                        data=message_data.get("data", {}),
                    )
                else:
                    message = ConnectionMessage(
                        type=message_type,
                        client_id=client_id,
                        message=message_data.get("message", ""),
                    )

                # Broadcast usando el modelo
                await manager.broadcast(message.dict())

            except json.JSONDecodeError:
                error_message = ErrorMessage(
                    type="error", client_id=client_id, message="Formato JSON inválido"
                )
                await manager.send_personal_message(error_message.dict(), websocket)

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        disconnect_message = ConnectionMessage(
            type="client_disconnected",
            client_id=client_id,
            message="Cliente desconectado",
        )
        await manager.broadcast(disconnect_message.dict())
