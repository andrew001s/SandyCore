import json
import re
import time

from pydantic import BaseModel

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

    async def generate_text(self, message: str, system_instruction: str) -> str:
        start = time.perf_counter()
        print(f"[OPENROUTER] Enviando prompt a {self.model}...")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": message},
                ],
            )
            result = self._extract_content(response)
        except Exception as exc:
            raise Exception(f"OpenRouter falló al generar texto: {repr(exc)}") from exc

        elapsed = time.perf_counter() - start
        print(f"[OPENROUTER] Respuesta en {elapsed:.2f}s")
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
            )
            result = self._extract_content(response) or "¿Mande?"
            elapsed2 = time.perf_counter() - start2
            print(f"[OPENROUTER] Reintento exitoso en {elapsed2:.2f}s")
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
        return response_model(**parsed)
