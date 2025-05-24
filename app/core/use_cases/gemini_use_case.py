from app.adapters.gemini_services import GeminiServices

class GeminiServicesUseCase:
    def __init__(self, gemini_services:GeminiServices):
        self.gemini_services = gemini_services
    async def execute(self, message: str) -> str:
        return await self.gemini_services.response_sandy_shandrew(message)