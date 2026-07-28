import time

from pydantic import BaseModel

from app.core.config import config
from app.core.ports.ai_port import AIPort


class GeminiAdapter(AIPort):
    def __init__(self):
        from google import genai

        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = "gemini-2.0-flash"

    async def generate_text(self, message: str, system_instruction: str) -> str:
        start = time.perf_counter()
        print(f"[GEMINI] Enviando prompt a {self.model}...")
        from google.genai import types

        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            ),
        )
        result = chat.send_message(message).text
        elapsed = time.perf_counter() - start
        print(f"[GEMINI] Respuesta en {elapsed:.2f}s ({len(result)} chars): {result[:200]}")
        return result

    async def generate_structured(
        self, content: str, response_model: type[BaseModel]
    ) -> BaseModel:
        start = time.perf_counter()
        print(f"[GEMINI] Enviando prompt estructurado a {self.model}...")
        response = self.client.models.generate_content(
            model=self.model,
            contents=content,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_model,
            },
        )
        elapsed = time.perf_counter() - start
        print(f"[GEMINI] Respuesta estructurada en {elapsed:.2f}s")
        return response.parsed
