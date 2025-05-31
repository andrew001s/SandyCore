from app.adapters.twitch_services import TwitchService

class StopServicesUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self):
        await self.twitch_service.close_chat()
        await self.twitch_service.close_eventsub()
        
