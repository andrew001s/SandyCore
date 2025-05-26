from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
from datetime import datetime

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
        # Enviar mensaje de bienvenida
        await manager.send_personal_message({
            "type": "connection_established",
            "client_id": client_id,
            "message": "Conectado al servidor WebSocket",
            "timestamp": datetime.now().isoformat()
        }, websocket)

        while True:
            try:
                # Recibir datos como texto y convertir a JSON
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Procesar el mensaje según su tipo
                if "type" not in message_data:
                    message_data["type"] = "message"
                    
                # Añadir metadatos al mensaje
                response = {
                    **message_data,
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Broadcast del mensaje a todos los clientes
                await manager.broadcast(response)
                
            except json.JSONDecodeError:
                # Si el mensaje no es JSON válido, enviar error
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Formato JSON inválido",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        # Notificar a otros clientes de la desconexión
        await manager.broadcast({
            "type": "client_disconnected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })
