"""Puente para que el backend use el modelo local del usuario.

El backend no alcanza `http://localhost:11434`, pero el navegador sí. Cuando el
proveedor es `local`, el backend publica la petición por el canal SSE de ese
usuario y espera la respuesta, que el navegador devuelve por HTTP.

Se usa solo para lo que arranca en el backend —mensajes de chat, moderación,
eventos y recompensas—. Lo que arranca en el navegador (el dictáfono) sigue
hablando directo con el modelo local, sin pasar por aquí.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from app.adapters.websocket_adapter import WebsocketAdapter
from app.controllers.websocket.websocket_server import manager
from app.domain.errors import (
    LOCAL_PROVIDER_UNREACHABLE,
    TIMEOUT,
    AppError,
    classify_error,
)

# La inferencia local puede ser lenta; el plazo es generoso pero acotado para no
# dejar peticiones colgadas para siempre.
DEFAULT_TIMEOUT_SECONDS = 180.0

_pending: dict[str, asyncio.Future[str]] = {}
_adapter = WebsocketAdapter()


def has_listener(user_id: str) -> bool:
    """¿Hay alguna pestaña de este usuario escuchando el bus?"""
    owner = str(user_id)
    return manager.stream_count(owner) > 0 or manager.connection_count_for(owner) > 0


def pending_count() -> int:
    return len(_pending)


async def request_completion(
    user_id: str,
    *,
    message: str,
    system_instruction: str,
    kind: str = "text",
    stop: list[str] | None = None,
    timeout: float | None = None,
) -> str:
    owner = str(user_id)
    if not has_listener(owner):
        raise AppError(
            LOCAL_PROVIDER_UNREACHABLE,
            "No hay ninguna pestaña abierta para atender el modelo local. "
            "Abre el panel de Sandy para que pueda responder al chat.",
            provider="local",
        )

    request_id = uuid4().hex
    future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    _pending[request_id] = future

    try:
        await _adapter.broadcast_message(
            {
                "id": f"ai_request_{request_id}",
                "type": "ai_request",
                "requestId": request_id,
                # 'moderation' distingue la evaluación de un mensaje sospechoso
                # de la generación de una respuesta.
                "kind": kind,
                "message": message,
                "systemInstruction": system_instruction,
                "stop": stop or [],
                "metadata": {"source": "ai_relay", "user_id": owner},
            },
            owner,
        )
        # El plazo se lee en cada llamada, no como valor por defecto del
        # parámetro, para poder ajustarlo sin reiniciar el proceso.
        return await asyncio.wait_for(future, timeout or DEFAULT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise AppError(
            TIMEOUT,
            "El modelo local no respondió a tiempo.",
            provider="local",
            detail=f"sin respuesta del navegador en {timeout or DEFAULT_TIMEOUT_SECONDS:.0f}s",
        ) from exc
    finally:
        _pending.pop(request_id, None)


def resolve(request_id: str, text: str) -> bool:
    """El navegador entrega el texto de su modelo. Devuelve si alguien esperaba."""
    future = _pending.get(request_id)
    if future is None or future.done():
        return False
    future.set_result(text)
    return True


def fail(request_id: str, code: str | None = None, message: str | None = None) -> bool:
    """El navegador informa de un fallo con su modelo local."""
    future = _pending.get(request_id)
    if future is None or future.done():
        return False
    error = (
        AppError(code, message, provider="local")
        if code
        else classify_error(
            Exception(message or "fallo del modelo local"), provider="local"
        )
    )
    future.set_exception(error)
    return True
