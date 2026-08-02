from app.adapters.kick_services import KickService


class KickAuthUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id, token, refresh_token, bot: bool = False):
        kick, kick_bot, profile_id = await self.kick_service.create_instance(
            user_id, token, refresh_token, bot
        )
        try:
            await self.kick_service.subscribe_chat_events(user_id, bot)
        except Exception as exc:
            print(f"[KICK AUTH] No se pudo suscribir al webhook de chat: {repr(exc)}")
        return kick, kick_bot, profile_id
