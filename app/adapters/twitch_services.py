from app.services.twitch.twitch import auth, setup_eventsub,setup_chat, close_chat, close_eventsub
import twitchAPI.type as type
from app.domain.exceptions import EventSubError

class TwitchService:
    async def create_instance(self,  token: str = None, refresh_token: str = None,bot: bool = False,):
        return await auth.create_twitch_instance(bot, token, refresh_token)

    async def return_instance(self, bot: bool = False):
        return await auth.return_twitch_instance(bot)
    
    async def setup_chat(self, twitch_obj):
        await setup_chat(twitch_obj)

    async def close_chat(self):
        await close_chat()

    async def setup_eventsub(self, twitch, user_id):
        try:
            await setup_eventsub(twitch, user_id)
        except type.EventSubSubscriptionError as e:
            raise EventSubError(str(e))
    
    async def close_twitch(self):
        await auth.close_twitch()
    
    async def close_eventsub(self):
        await close_eventsub()