from app.domain.exceptions import EventSubError
from app.models.ProfileModel import ProfileModel


class TwitchService:
    async def create_instance(
        self,
        user_id: str | None = None,
        token: str = None,
        refresh_token: str = None,
        bot: bool = False,
    ):
        from app.services.twitch.twitch import auth

        return await auth.create_twitch_instance(user_id, bot, token, refresh_token)

    async def get_profile(self, user_id: str | None = None, bot: bool = False):
        from app.services.twitch.twitch import auth

        user = await auth.get_profile_users(bot, user_id)
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

    async def setup_chat(self, twitch_obj, twitch_bot=None, user_id: str | None = None):
        from app.services.twitch.twitch import setup_chat_instance as setup_chat

        await setup_chat(twitch_obj, twitch_bot, user_id)

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
        from app.services.twitch.twitch import close_twitch as close_twitch_service

        await close_twitch_service()

    async def logout_twitch(self):
        from app.services.twitch.twitch import logout_twitch as logout_twitch_service

        await logout_twitch_service()

    async def close_eventsub(self):
        from app.services.twitch.twitch import close_eventsub

        await close_eventsub()

    async def get_tokens(self, user_id: str | None = None, bot: bool = False):
        from app.services.twitch.twitch import auth

        return await auth.get_tokens(user_id, bot)

    async def save_tokens(
        self,
        user_id: str | None = None,
        bot: bool = False,
        token: str = None,
        refresh_token: str = None,
    ):
        from app.services.twitch.twitch import auth

        return await auth.save_tokens(user_id, token, refresh_token, bot)
