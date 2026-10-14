"""Cliente HTTP compartido por todo el proceso.

Crear un `httpx.AsyncClient` por petición monta cada vez un contexto SSL nuevo
(con la carga de certificados de certifi) y un pool de conexiones que se tira
al terminar. Con el monitor de YouTube sondeando cada pocos segundos eso era
memoria y CPU quemadas en bucle, además de fragmentar el heap. Un solo cliente
reutiliza conexiones y contexto SSL.

El timeout se puede seguir ajustando por petición con `timeout=`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(30.0)
_LIMITS = httpx.Limits(
    max_connections=50,
    max_keepalive_connections=10,
    keepalive_expiry=30.0,
)

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Devuelve el cliente compartido, creándolo la primera vez."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, limits=_LIMITS)
    return _client


async def close_http_client() -> None:
    """Solo para el apagado del proceso."""
    global _client
    client, _client = _client, None
    if client is not None and not client.is_closed:
        await client.aclose()


@asynccontextmanager
async def shared_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Sustituto directo de `async with httpx.AsyncClient() as c:`.

    Entrega el cliente compartido y NO lo cierra al salir del bloque.
    """
    yield get_http_client()
