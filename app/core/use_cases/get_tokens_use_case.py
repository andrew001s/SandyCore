from app.adapters.twitch_services import TwitchService

class GetTokensUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service
    
    async def execute(self, bot: bool = False):
        tokens = await self.twitch_service.get_tokens(bot)
        return tokens
