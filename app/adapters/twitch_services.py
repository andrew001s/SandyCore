import twitchAPI.type as type

from app.domain.exceptions import EventSubError
from app.models.ProfileModel import ProfileModel
from app.services.twitch.twitch import auth, close_chat, close_eventsub
from app.services.twitch.twitch import setup_chat_instance as setup_chat
from app.services.twitch.twitch import setup_eventsub_instance as setup_eventsub


class TwitchService:
    async def create_instance(
        self,
        token: str = None,
        refresh_token: str = None,
        bot: bool = False,
    ):
        return await auth.create_twitch_instance(bot, token, refresh_token)

    async def get_profile(self, bot: bool = False):
        user = await auth.get_profile_users(bot)
        if user is None:
            raise Exception("Usuario no autenticado")

        try:
            profile = ProfileModel(
                id=int(user.id),
                username=str(user.display_name),
                email=str(user.email),
                picProfile=str(user.profile_image_url),
                broadcaster_type=str(user.broadcaster_type),
            )
            return profile.model_dump()
        except Exception as e:
            raise Exception(f"Error al mapear el perfil: {str(e)}")

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

    async def get_tokens(self, bot: bool = False):
        return await auth.get_tokens(bot)

    async def save_tokens(
        self, bot: bool = False, token: str = None, refresh_token: str = None
    ):
        if not bot:
            return await auth.save_tokens(token, refresh_token)
        else:
            return await auth.save_bot_tokens(token, refresh_token)
