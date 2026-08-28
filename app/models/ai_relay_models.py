from typing import Optional

from pydantic import BaseModel


class AiRelayResultModel(BaseModel):
    """Respuesta que el navegador devuelve tras consultar su modelo local.

    Con `partial` en True el trozo se añade y la petición sigue abierta; el
    último envío va sin él y cierra la respuesta.
    """

    request_id: str
    text: Optional[str] = None
    partial: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
