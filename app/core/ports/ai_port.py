from abc import ABC, abstractmethod

from pydantic import BaseModel


class AIPort(ABC):
    @abstractmethod
    async def generate_text(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ) -> str:
        """Genera texto.

        `stop` son secuencias que cortan la generación. Se usan para impedir que
        el modelo siga escribiendo el turno siguiente de la conversación.
        """

    @abstractmethod
    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        pass
