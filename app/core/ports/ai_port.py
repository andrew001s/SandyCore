from abc import ABC, abstractmethod
from typing import AsyncIterator

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
    def generate_text_stream(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Igual que `generate_text`, pero entregando el texto según se genera.

        Devuelve los fragmentos crudos del proveedor: limpiarlos es cosa de la
        capa de servicio, que necesita ver marcas completas para hacerlo bien.
        """

    @abstractmethod
    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        pass
