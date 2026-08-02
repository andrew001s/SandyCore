from app.adapters.kick_services import KickService


class SaveKickTokensUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(
        self, user_id: str | None = None, bot: bool = False, token: str = None, refresh_token: str = None
    ):
        return await self.kick_service.save_tokens(user_id, bot, token, refresh_token)
