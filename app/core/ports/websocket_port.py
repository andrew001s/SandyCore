from abc import ABC, abstractmethod
from typing import Any, Dict


class WebsocketPort(ABC):
    @abstractmethod
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        pass
