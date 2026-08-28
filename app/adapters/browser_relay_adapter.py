"""Proveedor de IA que delega la inferencia en el navegador del usuario.

Implementa el mismo puerto que Gemini y OpenRouter, así que todas las rutas del
backend —chat de Twitch, moderación, eventos, recompensas, órdenes, estadísticas
e historial— funcionan sin enterarse de que el modelo vive en la máquina del
usuario en vez de en la nube.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.core.ports.ai_port import AIPort
from app.services import ai_relay


def _extract_json(raw: str) -> str:
    texto = (raw or "").strip()
    if texto.startswith("```"):
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", texto)
        if match:
            return match.group(1).strip()
    inicio = texto.find("{")
    return texto[inicio:] if inicio != -1 else texto


class BrowserRelayAdapter(AIPort):
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.model = "local"

    async def generate_text(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ) -> str:
        return await ai_relay.request_completion(
            self.user_id,
            message=message,
            system_instruction=system_instruction,
            kind="text",
            stop=stop,
        )

    async def generate_text_stream(
        self,
        message: str,
        system_instruction: str,
        stop: list[str] | None = None,
    ):
        # El navegador va enviando trozos según los produce su modelo, así que
        # aquí se reenvían igual que los de Gemini u OpenRouter.
        async for chunk in ai_relay.stream_completion(
            self.user_id,
            message=message,
            system_instruction=system_instruction,
            kind="text",
            stop=stop,
        ):
            yield chunk

    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        raw = await ai_relay.request_completion(
            self.user_id,
            message=content,
            system_instruction=(
                "Responde únicamente con un objeto JSON válido, sin texto "
                "alrededor ni bloques de código."
            ),
            kind="structured",
        )
        try:
            parsed = json.loads(_extract_json(raw))
        except Exception:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("type", "interacción")
        try:
            return response_model(**parsed)
        except ValidationError:
            return response_model()
