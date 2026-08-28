from app.adapters.twitch_services import TwitchService
from app.services.twitch.lifecycle import stop_services


class StopServicesUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str | None = None):
        print(f"[TWITCH STOP] Pausando servicios para user_id={user_id}")
        await stop_services(user_id)
