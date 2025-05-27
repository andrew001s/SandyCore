from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime

class WebSocketBaseMessage(BaseModel):
    type: str
    client_id: Optional[int] = None
    timestamp: str = datetime.now().isoformat()

class ChatMessage(WebSocketBaseMessage):
    messages: List[str]
    response: str

class ErrorMessage(WebSocketBaseMessage):
    message: str

class ConnectionMessage(WebSocketBaseMessage):
    message: str

class NotificationMessage(WebSocketBaseMessage):
    event_type: str
    data: Dict[str, Any]
