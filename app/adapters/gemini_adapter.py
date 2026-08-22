import time
import traceback

from pydantic import BaseModel

from app.core.ports.ai_port import AIPort


def _unwrap_error(exc: BaseException) -> BaseException:
    """Desenvuelve el RetryError con el que el SDK de Gemini tapa el error real.

    Sin `http_options.retry_options`, el SDK envuelve la llamada en un
    `tenacity.Retrying(stop=stop_after_attempt(1))`. Al no llevar `reraise`,
    cualquier excepción sale como `RetryError(<Future ... raised ClientError>)`,
    sin el código HTTP ni el mensaje de la API, que es justo lo que hace falta
    para saber si fue cuota, credencial o modelo inexistente.
    """
    seen: set[int] = set()
    current: BaseException = exc
    while id(current) not in seen:
        seen.add(id(current))
        last_attempt = getattr(current, "last_attempt", None)
        if last_attempt is None or not hasattr(last_attempt, "exception"):
            break
        try:
            inner = last_attempt.exception()
        except Exception:
            break
        if inner is None:
            break
        current = inner
    return current


def _describe_error(exc: BaseException) -> str:
    real = _unwrap_error(exc)
    code = getattr(real, "code", None)
    message = getattr(real, "message", None)
    if code is not None or message:
        detalle = f"{type(real).__name__} {code if code is not None else ''}".strip()
        return f"{detalle}: {message}" if message else detalle
    return repr(real)


def _extract_text(response) -> str | None:
    text = getattr(response, "text", None)
    if text:
        return text
    # Sin texto: casi siempre es un bloqueo por filtros de seguridad o un corte
    # por longitud. El motivo viaja en el candidato o en el prompt_feedback.
    motivos = []
    for candidate in getattr(response, "candidates", None) or []:
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason:
            motivos.append(str(finish_reason))
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None:
        motivos.append(f"prompt_feedback={feedback}")
    if motivos:
        print(f"[GEMINI] Respuesta sin texto ({', '.join(motivos)})")
    else:
        print("[GEMINI] Respuesta sin texto y sin motivo declarado")
    return None


class GeminiAdapter(AIPort):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    # Gemini admite hasta 5 secuencias de parada.
    MAX_STOP_SEQUENCES = 5

    async def _call(self, message: str, system_instruction: str, stop_sequences: list[str]):
        from google.genai import types

        # `client.aio` es la API asíncrona. La versión síncrona bloqueaba el
        # event loop durante toda la llamada, congelando de paso el chat,
        # EventSub y los streams SSE del resto de usuarios del proceso.
        return await self.client.aio.models.generate_content(
            model=self.model,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                stop_sequences=stop_sequences or None,
            ),
        )

    async def generate_text(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ) -> str:
        start = time.perf_counter()
        print(f"[GEMINI] Enviando prompt a {self.model}...")
        stop_sequences = [s for s in (stop or []) if s][: self.MAX_STOP_SEQUENCES]

        try:
            response = await self._call(message, system_instruction, stop_sequences)
            result = _extract_text(response)

            # Si el modelo arranca con su propia etiqueta, la secuencia de parada
            # salta en el carácter cero y devuelve vacío. Se reintenta sin ellas y
            # el saneador de la capa superior recorta el turno sobrante.
            if not result and stop_sequences:
                print(
                    "[GEMINI] ADVERTENCIA: vacío con secuencias de parada, "
                    "reintentando sin ellas..."
                )
                response = await self._call(message, system_instruction, [])
                result = _extract_text(response)
        except Exception as exc:
            detalle = _describe_error(exc)
            print(f"[GEMINI] ERROR al generar texto: {detalle}")
            print(traceback.format_exc())
            raise Exception(f"Gemini falló al generar texto: {detalle}") from exc

        elapsed = time.perf_counter() - start
        if not result:
            raise Exception("Gemini devolvió una respuesta vacía")
        print(f"[GEMINI] Respuesta en {elapsed:.2f}s ({len(result)} chars): {result[:200]}")
        return result

    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        start = time.perf_counter()
        print(f"[GEMINI] Enviando prompt estructurado a {self.model}...")
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=content,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": response_model,
                },
            )
        except Exception as exc:
            detalle = _describe_error(exc)
            print(f"[GEMINI] ERROR al generar estructura: {detalle}")
            print(traceback.format_exc())
            raise Exception(f"Gemini falló al generar estructura: {detalle}") from exc

        elapsed = time.perf_counter() - start
        print(f"[GEMINI] Respuesta estructurada en {elapsed:.2f}s")
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            print("[GEMINI] ADVERTENCIA: structured sin parsear, usando fallback")
            return response_model()
        return parsed
