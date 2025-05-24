from app.services.gemini import response_sandy_shandrew

class GeminiServices: 
    async def response_sandy_shandrew(self, message: str) -> str:
        return await response_sandy_shandrew(message)