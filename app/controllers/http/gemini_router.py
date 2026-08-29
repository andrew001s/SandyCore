import json

from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.adapters.gemini_services import GeminiServices
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.use_cases.gemini_use_case import GeminiServicesUseCase
from app.domain.errors import error_payload
from app.domain.ai_errors import UNKNOWN, AIProviderError, classify_ai_error
from app.models.ai_relay_models import AiRelayResultModel, AiTaskResultModel
from app.models.message_model import MessageModel
from app.services import ai_relay
from app.services.gemini import (
    build_local_context,
    record_local_task,
    stream_sandy_shandrew,
)

router = APIRouter(tags=["AI"])


@router.post("/gemini")
async def gemini_response_sandy_shandrew(
    message_payload: MessageModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    use_case = GeminiServicesUseCase(GeminiServices())
    try:
        response = await use_case.execute(message_payload.message, current_user.user_id)
        return JSONResponse(status_code=200, content={"message": response})
    except AIProviderError as exc:
        # El cuerpo lleva un código estable: el cliente elige el texto que ve el
        # usuario sin tener que leer el mensaje crudo del proveedor.
        print(f"[GEMINI ROUTER] {exc!r}")
        return JSONResponse(
            status_code=exc.http_status, content={"error": exc.to_payload()}
        )
    except Exception as exc:
        # Cualquier otro fallo se clasifica igual para que el contrato de la
        # respuesta de error sea siempre el mismo.
        error = classify_ai_error(exc)
        if error.code == UNKNOWN:
            print(f"[GEMINI ROUTER] error no clasificado: {exc!r}")
        return JSONResponse(
            status_code=error.http_status, content={"error": error.to_payload()}
        )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/gemini/stream")
async def gemini_stream(
    message_payload: MessageModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    """Misma respuesta que POST /gemini, pero entregada según se genera.

    Eventos SSE:
      delta {"text": "..."}   fragmento listo para mostrar o sintetizar
      done  {"message": "..."} texto completo (la concatenación de los deltas)
      error {"code", "message", ...}  mismo contrato que el endpoint no-streaming
    """

    async def event_generator():
        partes: list[str] = []
        try:
            async for piece in stream_sandy_shandrew(
                message_payload.message, current_user.user_id
            ):
                partes.append(piece)
                yield _sse("delta", {"text": piece})
            yield _sse("done", {"message": "".join(partes)})
        except AIProviderError as exc:
            print(f"[GEMINI STREAM] {exc!r}")
            yield _sse("error", exc.to_payload())
        except Exception as exc:
            error = classify_ai_error(exc)
            if error.code == UNKNOWN:
                print(f"[GEMINI STREAM] error no clasificado: {exc!r}")
            yield _sse("error", error.to_payload())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/ai/local/context")
async def local_ai_context(current_user: ClerkUser = Depends(verify_clerk_session)):
    """Prompts y personalidad para un modelo local.

    El navegador llama directo a su modelo, así que necesita el system prompt
    que el backend usa con Gemini y OpenRouter: reglas base, formato de salida,
    perfil del personaje e historial de la conversación.
    """
    try:
        contexto = await build_local_context(current_user.user_id)
        return JSONResponse(status_code=200, content={"context": contexto})
    except Exception as exc:
        status_code, body = error_payload(exc)
        return JSONResponse(status_code=status_code, content=body)


@router.post("/ai/local/result")
async def local_relay_result(
    payload: AiRelayResultModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    """El navegador entrega el resultado de su modelo local.

    La petición la abrió el backend por el canal SSE de este mismo usuario; aquí
    solo se desbloquea a quien estaba esperando. Que ya no espere nadie no es un
    error: pudo vencer el plazo mientras el modelo generaba.
    """
    try:
        if payload.error_code or payload.error_message:
            entregado = ai_relay.fail(
                payload.request_id, payload.error_code, payload.error_message
            )
        else:
            entregado = ai_relay.resolve(
                payload.request_id, payload.text or "", payload.partial
            )
        return JSONResponse(
            status_code=200,
            content={"delivered": entregado, "pending": ai_relay.pending_count()},
        )
    except Exception as exc:
        status_code, body = error_payload(exc)
        return JSONResponse(status_code=status_code, content=body)


@router.post("/ai/local/task-result")
async def local_task_result(
    payload: AiTaskResultModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    """El navegador informa del texto con el que respondió a una tarea local.

    No sirve para hablar —eso ya lo hizo el navegador— sino para que el backend
    limpie el texto y lo guarde en el historial de la conversación.
    """
    try:
        clean = await record_local_task(
            payload.message, payload.response, current_user.user_id
        )
        return JSONResponse(status_code=200, content={"message": clean})
    except Exception as exc:
        status_code, body = error_payload(exc)
        return JSONResponse(status_code=status_code, content=body)
