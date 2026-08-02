from app.adapters.kick_services import KickService


class GetKickProfileUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str | None = None, bot: bool = False):
        user = await self.kick_service.get_profile(user_id, bot)
        return user
