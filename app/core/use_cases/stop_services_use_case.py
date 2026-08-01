from app.adapters.twitch_services import TwitchService
from app.services.twitch.lifecycle import disarm


class StopServicesUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str | None = None):
        await disarm(user_id)
