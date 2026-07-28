from app.domain.exceptions import EventSubError
from app.models.ProfileModel import ProfileModel


class TwitchService:
    async def create_instance(
        self,
        token: str = None,
        refresh_token: str = None,
        bot: bool = False,
    ):
        from app.services.twitch.twitch import auth

        return await auth.create_twitch_instance(bot, token, refresh_token)

    async def get_profile(self, bot: bool = False):
        from app.services.twitch.twitch import auth

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
        from app.services.twitch.twitch import auth

        return await auth.return_twitch_instance(bot)

    async def setup_chat(self, twitch_obj, twitch_bot=None):
        from app.services.twitch.twitch import setup_chat_instance as setup_chat

        await setup_chat(twitch_obj, twitch_bot)

    async def close_chat(self):
        from app.services.twitch.twitch import close_chat_instance as close_chat

        await close_chat()

    async def setup_eventsub(self, twitch, user_id):
        try:
            import twitchAPI.type as type
            from app.services.twitch.twitch import (
                setup_eventsub_instance as setup_eventsub,
            )

            await setup_eventsub(twitch, user_id)
        except type.EventSubSubscriptionError as e:
            raise EventSubError(str(e))

    async def close_twitch(self):
        from app.services.twitch.twitch import auth

        await auth.close_twitch()

    async def close_eventsub(self):
        from app.services.twitch.twitch import close_eventsub

        await close_eventsub()

    async def get_tokens(self, bot: bool = False):
        from app.services.twitch.twitch import auth

        return await auth.get_tokens(bot)

    async def save_tokens(
        self, bot: bool = False, token: str = None, refresh_token: str = None
    ):
        from app.services.twitch.twitch import auth

        if not bot:
            return await auth.save_tokens(token, refresh_token)
        else:
            return await auth.save_bot_tokens(token, refresh_token)
