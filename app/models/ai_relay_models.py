from typing import Optional

from pydantic import BaseModel


class AiRelayResultModel(BaseModel):
    """Respuesta que el navegador devuelve tras consultar su modelo local."""

    request_id: str
    text: Optional[str] = None
    # Con partial=True la petición sigue abierta y llegarán más trozos.
    partial: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
