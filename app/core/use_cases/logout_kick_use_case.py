from app.adapters.kick_services import KickService


class LogoutKickUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str | None = None):
        await self.kick_service.logout_kick(user_id)
