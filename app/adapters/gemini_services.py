from app.services.gemini import response_sandy_shandrew


class GeminiServices:
    async def response_sandy_shandrew(self, message: str, user_id: str | None = None) -> str:
        response = await response_sandy_shandrew(message, user_id)
        from app.services.client_settings import load_effective_settings
        from app.services.twitch.chat.chat_handler import send_twitch_message

        settings = await load_effective_settings(user_id)
        feature_flags = settings.get("feature_flags") or {}
        if not feature_flags.get("voice_replies", True):
            await send_twitch_message(response, user_id)
        return response
