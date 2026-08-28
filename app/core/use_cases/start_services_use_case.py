from app.adapters.twitch_services import TwitchService
from app.domain.exceptions import EventSubError
from app.services.twitch.lifecycle import set_running


class StartServicesCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str, bot: bool = False):
        try:
            twitch, twitch_bot, twitch_user_id = await self.twitch_service.return_instance(
                bot, user_id
            )
            if bot:
                await self.twitch_service.setup_chat(
                    twitch_bot, twitch_bot=twitch, user_id=user_id
                )
            else:
                await self.twitch_service.setup_chat(twitch, user_id=user_id)

            try:
                await self.twitch_service.setup_eventsub(
                    twitch, user_id, twitch_user_id
                )
            except EventSubError:
                pass
            except Exception as e:
                print(f"Error al iniciar EventSub: {e}")

            await set_running(user_id, True)
        except Exception as e:
            print(f"Error al iniciar servicios: {e}")
