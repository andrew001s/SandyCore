from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
from datetime import datetime
from app.models.websocket_models import (
    ChatMessage, 
    ErrorMessage, 
    ConnectionMessage, 
    NotificationMessage
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_count = 0

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_count += 1
        return self.connection_count

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            await connection.send_json(message)
            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

async def handle_websocket(websocket: WebSocket):
    client_id = await manager.connect(websocket)
    try:
        # Enviar mensaje de bienvenida usando el modelo
        welcome_message = ConnectionMessage(
            type="connection_established",
            client_id=client_id,
            message="Conectado al servidor WebSocket"
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
                        response=message_data.get("response", "")
                    )
                elif message_type == "notification":
                    message = NotificationMessage(
                        type=message_type,
                        client_id=client_id,
                        event_type=message_data.get("event_type", ""),
                        data=message_data.get("data", {})
                    )
                else:
                    message = ConnectionMessage(
                        type=message_type,
                        client_id=client_id,
                        message=message_data.get("message", "")
                    )
                
                # Broadcast usando el modelo
                await manager.broadcast(message.dict())
                
            except json.JSONDecodeError:
                error_message = ErrorMessage(
                    type="error",
                    client_id=client_id,
                    message="Formato JSON inválido"
                )
                await manager.send_personal_message(error_message.dict(), websocket)
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        disconnect_message = ConnectionMessage(
            type="client_disconnected",
            client_id=client_id,
            message="Cliente desconectado"
        )
        await manager.broadcast(disconnect_message.dict())
