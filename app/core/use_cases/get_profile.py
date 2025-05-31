from app.adapters.twitch_services import TwitchService
from app.models.ProfileModel import ProfileModel

class GetProfileUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service
    
    async def execute(self, bot: bool = False) -> ProfileModel:
        user = await self.twitch_service.get_profile(bot)
        return user
