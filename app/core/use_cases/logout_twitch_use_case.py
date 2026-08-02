from app.adapters.twitch_services import TwitchService


class LogoutTwitchUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self):
        print("[TWITCH LOGOUT] Cerrando sesión de Twitch")
        await self.twitch_service.logout_twitch()
