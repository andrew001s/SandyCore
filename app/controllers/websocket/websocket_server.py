import asyncio
import json
from typing import Any, Dict, List

from fastapi import WebSocket, WebSocketDisconnect

from app.core.security.stream_token import verify_stream_token
from app.models.websocket_models import (
    ChatMessage,
    ConnectionMessage,
    ErrorMessage,
    NotificationMessage,
)


class ConnectionManager:
    """Bus de eventos en tiempo real, particionado por usuario.

    Cada conexión y cada cola SSE queda registrada bajo el user_id que la
    autenticó, y `broadcast` entrega SOLO a ese usuario. Un único registro
    global haría que el chat, las respuestas de IA y los eventos de un
    streamer llegaran al overlay de todos los demás.
    """

    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._streams: Dict[str, List[asyncio.Queue[Dict[str, Any]]]] = {}
        self.connection_count = 0

    # ------------------------------------------------------------------ websockets

    async def connect(self, websocket: WebSocket, user_id: str) -> int:
        await websocket.accept()
        self._connections.setdefault(str(user_id), []).append(websocket)
        self.connection_count += 1
        return self.connection_count

    async def disconnect(self, websocket: WebSocket, user_id: str | None = None):
        owners = [str(user_id)] if user_id is not None else list(self._connections)
        for owner in owners:
            connections = self._connections.get(owner)
            if not connections or websocket not in connections:
                continue
            connections.remove(websocket)
            if not connections:
                self._connections.pop(owner, None)

    # ------------------------------------------------------------------ streams SSE

    async def connect_stream(self, user_id: str) -> asyncio.Queue[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._streams.setdefault(str(user_id), []).append(queue)
        return queue

    async def disconnect_stream(
        self, queue: asyncio.Queue[Dict[str, Any]], user_id: str | None = None
    ):
        owners = [str(user_id)] if user_id is not None else list(self._streams)
        for owner in owners:
            queues = self._streams.get(owner)
            if not queues or queue not in queues:
                continue
            queues.remove(queue)
            if not queues:
                self._streams.pop(owner, None)

    # ------------------------------------------------------------------ entrega

    def _push_to_queue(self, queue: asyncio.Queue[Dict[str, Any]], message) -> None:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                _ = queue.get_nowait()
                queue.put_nowait(message)
            except Exception:
                return

    async def broadcast(self, message: Dict[str, Any], user_id: str) -> None:
        """Entrega el evento únicamente a las conexiones de este usuario."""
        owner = str(user_id)
        stale: List[WebSocket] = []
        for connection in list(self._connections.get(owner, [])):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)

        for connection in stale:
            await self.disconnect(connection, owner)

        for queue in list(self._streams.get(owner, [])):
            self._push_to_queue(queue, message)

    async def broadcast_all(self, message: Dict[str, Any]) -> None:
        """Anuncios del servidor a todo el mundo. Nunca para eventos de usuario."""
        for owner in list(self._connections) + list(self._streams):
            await self.broadcast(message, owner)

    async def send_personal_message(
        self, message: Dict[str, Any], websocket: WebSocket
    ):
        await websocket.send_json(message)

    # ------------------------------------------------------------------ introspección

    def stream_count(self, user_id: str) -> int:
        return len(self._streams.get(str(user_id), []))

    def connection_count_for(self, user_id: str) -> int:
        return len(self._connections.get(str(user_id), []))


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, token: str | None = None):
    if not token:
        await websocket.close(code=1008, reason="Falta el token de stream")
        return

    try:
        payload = verify_stream_token(token)
        user_id = str(payload["sub"])
    except Exception:
        await websocket.close(code=1008, reason="Token de stream inválido o expirado")
        return

    client_id = await manager.connect(websocket, user_id)
    try:
        welcome_message = ConnectionMessage(
            type="connection_established",
            client_id=client_id,
            message="✅ Conectado al servidor WebSocket",
        )
        await manager.send_personal_message(welcome_message.dict(), websocket)

        while True:
            try:
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

                # Lo que llega por el socket se reemite SOLO a la sesión de quien
                # lo envió. Reemitirlo a todos permitía a cualquiera inyectar
                # eventos falsos en el avatar de otro streamer.
                await manager.broadcast(message.dict(), user_id)

            except json.JSONDecodeError:
                error_message = ErrorMessage(
                    type="error", client_id=client_id, message="Formato JSON inválido"
                )
                await manager.send_personal_message(error_message.dict(), websocket)

    except WebSocketDisconnect:
        await manager.disconnect(websocket, user_id)
        disconnect_message = ConnectionMessage(
            type="client_disconnected",
            client_id=client_id,
            message="Cliente desconectado",
        )
        await manager.broadcast(disconnect_message.dict(), user_id)
