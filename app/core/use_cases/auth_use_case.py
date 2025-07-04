from app.adapters.twitch_services import TwitchService


class AuthUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, token, refresh_token, bot: bool = False):
        twitch, twitch_bot, user_id = await self.twitch_service.create_instance(
            token, refresh_token, bot
        )
        return twitch, twitch_bot, user_id
        """if bot:
            await self.twitch_service.setup_chat(twitch_bot)
        else:
            await self.twitch_service.setup_chat(twitch)

        try:
            await self.twitch_service.setup_eventsub(twitch, user_id)
        except EventSubError:
            pass
        except Exception as e:
            print(f"Error al iniciar EventSub: {e}")"""
