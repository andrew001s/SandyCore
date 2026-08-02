from app.adapters.kick_services import KickService


class GetKickTokensUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str | None = None, bot: bool = False):
        return await self.kick_service.get_tokens(user_id, bot)
