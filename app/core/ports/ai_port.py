from abc import ABC, abstractmethod

from pydantic import BaseModel


class AIPort(ABC):
    @abstractmethod
    async def generate_text(self, message: str, system_instruction: str) -> str:
        pass

    @abstractmethod
    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        pass
