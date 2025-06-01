from app.adapters.twitch_services import TwitchService
from app.domain.exceptions import EventSubError

class StartServicesCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service
    
    async def execute(self,bot: bool = False):
        twitch, twitch_bot, user_id = await self.twitch_service.return_instance(bot)
        if bot:            
            await self.twitch_service.setup_chat(twitch_bot)
        else:
            await self.twitch_service.setup_chat(twitch)

        try:
            await self.twitch_service.setup_eventsub(twitch, user_id)
        except EventSubError:
            pass 
        except Exception as e:
            print(f"Error al iniciar EventSub: {e}")
