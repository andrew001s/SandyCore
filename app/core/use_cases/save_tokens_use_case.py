from app.adapters.twitch_services import TwitchService


class SaveTokensUseCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(
        self,
        user_id: str,
        bot: bool = False,
        token: str = None,
        refresh_token: str = None,
    ):
        await self.twitch_service.save_tokens(user_id, bot, token, refresh_token)
