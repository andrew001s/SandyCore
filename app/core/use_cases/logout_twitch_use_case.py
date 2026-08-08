from app.adapters.twitch_services import TwitchService


class LogoutTwitchUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str | None = None):
        print(f"[TWITCH LOGOUT] Cerrando sesión de Twitch para user_id={user_id}")
        await self.twitch_service.logout_twitch(user_id)
