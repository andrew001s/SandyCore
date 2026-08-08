from abc import ABC, abstractmethod
from typing import Any, Dict


class WebsocketPort(ABC):
    @abstractmethod
    async def broadcast_message(self, message: Dict[str, Any], user_id: str) -> None:
        """Entrega el evento a las conexiones del usuario dueño del evento."""
