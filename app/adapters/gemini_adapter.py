import time
import traceback

from pydantic import BaseModel

from app.core.ports.ai_port import AIPort

# Se define aquí y se expone para que el resto del backend no repita la cadena.
# El valor efectivo sale de la configuración del usuario (ver `_get_ai_client`),
# así que cambiar de modelo no exige un despliegue.
#
# Ojo con el nombre: no existe un "gemini-3.1-flash" a secas. La familia 3.1
# solo publica la variante lite. Modelos Flash vigentes, del más capaz al más
# barato: gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash,
# gemini-3.5-flash-lite, gemini-3.1-flash-lite. Los 2.0 están apagados.
DEFAULT_GEMINI_MODEL = "gemini-3.7-flash"
from app.domain.ai_errors import (
    CONTENT_BLOCKED,
    EMPTY_RESPONSE,
    AIProviderError,
    classify_ai_error,
)


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
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL):
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
            error = classify_ai_error(exc, provider="gemini", model=self.model)
            print(f"[GEMINI] ERROR al generar texto: {error!r}")
            print(traceback.format_exc())
            raise error from exc

        elapsed = time.perf_counter() - start
        if not result:
            # `_extract_text` ya dejó el motivo en el log; si fue un bloqueo de
            # los filtros lo distinguimos para que el usuario sepa qué pasó.
            bloqueado = any(
                "SAFETY" in str(getattr(c, "finish_reason", "")).upper()
                for c in (getattr(response, "candidates", None) or [])
            )
            raise AIProviderError(
                CONTENT_BLOCKED if bloqueado else EMPTY_RESPONSE,
                provider="gemini",
                model=self.model,
            )
        print(f"[GEMINI] Respuesta en {elapsed:.2f}s ({len(result)} chars): {result[:200]}")
        return result

    async def generate_text_stream(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ):
        from google.genai import types

        start = time.perf_counter()
        print(f"[GEMINI] Streaming desde {self.model}...")
        stop_sequences = [s for s in (stop or []) if s][: self.MAX_STOP_SEQUENCES]
        recibido = 0

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    stop_sequences=stop_sequences or None,
                ),
            )
            async for chunk in stream:
                texto = getattr(chunk, "text", None)
                if texto:
                    recibido += len(texto)
                    yield texto
        except Exception as exc:
            error = classify_ai_error(exc, provider="gemini", model=self.model)
            print(f"[GEMINI] ERROR en streaming: {error!r}")
            raise error from exc

        elapsed = time.perf_counter() - start
        print(f"[GEMINI] Stream completo en {elapsed:.2f}s ({recibido} chars)")

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
            error = classify_ai_error(exc, provider="gemini", model=self.model)
            print(f"[GEMINI] ERROR al generar estructura: {error!r}")
            print(traceback.format_exc())
            raise error from exc

        elapsed = time.perf_counter() - start
        print(f"[GEMINI] Respuesta estructurada en {elapsed:.2f}s")
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            print("[GEMINI] ADVERTENCIA: structured sin parsear, usando fallback")
            return response_model()
        return parsed
