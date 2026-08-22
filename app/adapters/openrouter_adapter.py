import json
import re
import time

from pydantic import BaseModel, ValidationError

from app.core.ports.ai_port import AIPort


def _extract_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
        if match:
            return match.group(1).strip()
    if stripped.startswith("{"):
        return stripped
    brace_start = stripped.find("{")
    if brace_start != -1:
        return stripped[brace_start:]
    return stripped


class OpenRouterAdapter(AIPort):
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model

    @staticmethod
    def _extract_content(response) -> str | None:
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None:
            return None
        return getattr(message, "content", None)

    @staticmethod
    def _log_response(label: str, response) -> None:
        choices = getattr(response, "choices", None) or []
        print(f"[OPENROUTER] {label}: choices={len(choices)}")
        for index, choice in enumerate(choices[:3]):
            finish_reason = getattr(choice, "finish_reason", None)
            message = getattr(choice, "message", None)
            role = getattr(message, "role", None) if message is not None else None
            content = getattr(message, "content", None) if message is not None else None
            tool_calls = getattr(message, "tool_calls", None) if message is not None else None
            content_preview = ""
            if isinstance(content, str):
                content_preview = content[:200]
            print(
                "[OPENROUTER] "
                f"{label} choice[{index}]: "
                f"finish_reason={finish_reason}, "
                f"role={role}, "
                f"content_len={len(content) if isinstance(content, str) else 0}, "
                f"tool_calls={bool(tool_calls)}, "
                f"content={content_preview!r}"
            )

    # OpenAI acepta como mucho 4 secuencias de parada y algunos proveedores de
    # OpenRouter son más estrictos todavía; se recorta para no invalidar la
    # petición entera por un perfil con muchas etiquetas.
    MAX_STOP_SEQUENCES = 4

    def _messages(self, message: str, system_instruction: str) -> list[dict]:
        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": message},
        ]

    async def generate_text(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ) -> str:
        start = time.perf_counter()
        print(f"[OPENROUTER] Enviando prompt a {self.model}...")
        stop_sequences = [s for s in (stop or []) if s][: self.MAX_STOP_SEQUENCES]
        extra = {"stop": stop_sequences} if stop_sequences else {}

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._messages(message, system_instruction),
                **extra,
            )
            self._log_response("Respuesta inicial", response)
            result = self._extract_content(response)
        except Exception as exc:
            raise Exception(f"OpenRouter falló al generar texto: {repr(exc)}") from exc

        elapsed = time.perf_counter() - start
        print(f"[OPENROUTER] Respuesta en {elapsed:.2f}s")

        # Si el modelo arranca con su propia etiqueta, la secuencia de parada
        # salta en el carácter cero y devuelve vacío. Se reintenta sin ellas y
        # el saneador de la capa superior recorta el turno sobrante.
        if not result and stop_sequences:
            print(
                "[OPENROUTER] ADVERTENCIA: vacío con secuencias de parada, "
                "reintentando sin ellas..."
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._messages(message, system_instruction),
            )
            self._log_response("Reintento sin stop", response)
            result = self._extract_content(response)

        if result is None:
            print(
                "[OPENROUTER] ADVERTENCIA: respuesta vacía, reintentando sin system role..."
            )
            start2 = time.perf_counter()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": f"{system_instruction}\n\n{message}"},
                ],
                **extra,
            )
            self._log_response("Reintento", response)
            result = self._extract_content(response)
            elapsed2 = time.perf_counter() - start2
            print(f"[OPENROUTER] Reintento exitoso en {elapsed2:.2f}s")
        if not result:
            print("[OPENROUTER] ERROR: la respuesta sigue vacía tras el reintento.")
            result = "No pude generar una respuesta en este momento."
        print(f"[OPENROUTER] Respuesta ({len(result)} chars): {result[:200]}")
        return result

    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        start = time.perf_counter()
        print(f"[OPENROUTER] Enviando prompt estructurado a {self.model}...")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"},
            )
            raw = self._extract_content(response)
        except Exception as exc:
            raise Exception(f"OpenRouter falló al generar estructura: {repr(exc)}") from exc

        elapsed = time.perf_counter() - start
        print(f"[OPENROUTER] Respuesta estructurada en {elapsed:.2f}s")
        if raw is None:
            print(f"[OPENROUTER] ADVERTENCIA: respuesta nula en structured, usando fallback")
            return response_model(type="interacción", order_name=None, order_objective=None)
        print(f"[OPENROUTER] Raw: {raw[:200]}")
        parsed = json.loads(_extract_json(raw))
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("type", "interacción")
        try:
            return response_model(**parsed)
        except ValidationError:
            parsed["type"] = parsed.get("type") or "interacción"
            return response_model(**parsed)
