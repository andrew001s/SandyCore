"""Puente para usar el modelo local del usuario desde el backend.

El backend en la nube no alcanza a `http://localhost:11434`, pero el navegador
del usuario sí. Cuando el proveedor configurado es `local`, el backend publica
la petición por el canal SSE de ese usuario —el mismo bus particionado que ya
usan los eventos del avatar— y espera la respuesta, que el navegador devuelve
por HTTP.

Así ninguna funcionalidad se pierde: chat de Twitch, moderación, eventos,
recompensas, órdenes e historial siguen corriendo en el backend, que es donde
viven la persona, los prompts y el historial. Lo único que se delega es la
inferencia.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator
from uuid import uuid4

from app.adapters.websocket_adapter import WebsocketAdapter
from app.controllers.websocket.websocket_server import manager
from app.domain.errors import (
    LOCAL_PROVIDER_UNREACHABLE,
    TIMEOUT,
    AppError,
    classify_error,
)

# La inferencia local puede ser lenta en máquinas modestas; el corte es generoso
# a propósito, pero acotado para no dejar peticiones colgadas para siempre.
DEFAULT_TIMEOUT_SECONDS = 180.0

# Cada petición tiene una cola, no un Future: el navegador puede ir entregando
# la respuesta a trozos y así el backend la reenvía según llega, igual que hace
# con Gemini y OpenRouter. Los elementos son ("chunk", texto), ("end", None) o
# ("error", AppError).
_pending: dict[str, asyncio.Queue[tuple[str, Any]]] = {}
_adapter = WebsocketAdapter()


def has_listener(user_id: str) -> bool:
    """¿Hay algún navegador de este usuario escuchando el bus?"""
    owner = str(user_id)
    return manager.stream_count(owner) > 0 or manager.connection_count_for(owner) > 0


def pending_count() -> int:
    return len(_pending)


async def _open_request(
    owner: str,
    *,
    message: str,
    system_instruction: str,
    kind: str,
    stop: list[str] | None,
) -> str:
    if not has_listener(owner):
        raise AppError(
            LOCAL_PROVIDER_UNREACHABLE,
            "No hay ninguna pestaña abierta para atender el modelo local. "
            "Abre el panel de Sandy y vuelve a intentarlo.",
            provider="local",
        )

    request_id = uuid4().hex
    _pending[request_id] = asyncio.Queue()
    await _adapter.broadcast_message(
        {
            "id": f"ai_request_{request_id}",
            "type": "ai_request",
            "requestId": request_id,
            "kind": kind,
            "message": message,
            "systemInstruction": system_instruction,
            "stop": stop or [],
            "metadata": {"source": "ai_relay", "user_id": owner},
        },
        owner,
    )
    return request_id


async def stream_completion(
    user_id: str,
    *,
    message: str,
    system_instruction: str,
    kind: str = "text",
    stop: list[str] | None = None,
    timeout: float | None = None,
) -> AsyncIterator[str]:
    """Entrega la respuesta del modelo local según el navegador la va enviando."""
    owner = str(user_id)
    request_id = await _open_request(
        owner,
        message=message,
        system_instruction=system_instruction,
        kind=kind,
        stop=stop,
    )
    queue = _pending[request_id]

    try:
        while True:
            # El plazo se aplica a cada trozo, no al total: una respuesta larga
            # no debe vencer solo por serlo, pero un navegador mudo sí.
            try:
                tipo, valor = await asyncio.wait_for(
                    queue.get(), timeout or DEFAULT_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError as exc:
                raise AppError(
                    TIMEOUT,
                    "El modelo local no respondió a tiempo.",
                    provider="local",
                    detail=f"sin trozos del navegador en {timeout or DEFAULT_TIMEOUT_SECONDS:.0f}s",
                ) from exc

            if tipo == "chunk":
                if valor:
                    yield valor
            elif tipo == "error":
                raise valor
            else:
                return
    finally:
        _pending.pop(request_id, None)


async def request_completion(
    user_id: str,
    *,
    message: str,
    system_instruction: str,
    kind: str = "text",
    stop: list[str] | None = None,
    timeout: float | None = None,
) -> str:
    """Igual que `stream_completion`, pero devolviendo el texto ya completo."""
    partes: list[str] = []
    async for chunk in stream_completion(
        user_id,
        message=message,
        system_instruction=system_instruction,
        kind=kind,
        stop=stop,
        timeout=timeout,
    ):
        partes.append(chunk)
    return "".join(partes)


def _push(request_id: str, item: tuple[str, Any]) -> bool:
    queue = _pending.get(request_id)
    if queue is None:
        return False
    queue.put_nowait(item)
    return True


def resolve(request_id: str, text: str, partial: bool = False) -> bool:
    """El navegador entrega texto generado.

    Con `partial` se añade un trozo y la petición sigue abierta; sin él, se cierra.
    Devuelve si todavía había alguien esperando.
    """
    if not _push(request_id, ("chunk", text)):
        return False
    if not partial:
        _push(request_id, ("end", None))
    return True


def fail(request_id: str, code: str | None = None, message: str | None = None) -> bool:
    """El navegador informa de un fallo con su modelo local."""
    error = (
        AppError(code, message, provider="local")
        if code
        else classify_error(Exception(message or "fallo del modelo local"), provider="local")
    )
    return _push(request_id, ("error", error))


def payload_kind(value: Any) -> str:
    return "structured" if str(value).lower() == "structured" else "text"
