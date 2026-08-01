from app.adapters.twitch_services import TwitchService
from app.domain.exceptions import EventSubError
from app.services.client_settings import load_effective_settings
from app.services.twitch.lifecycle import (
    arm,
    register_activity_and_monitor,
    set_running,
    stop_monitor,
)


class StartServicesCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str, bot: bool = False):
        try:
            twitch, twitch_bot, twitch_user_id = await self.twitch_service.return_instance(
                bot
            )
            if bot:
                await self.twitch_service.setup_chat(
                    twitch_bot, twitch_bot=twitch, user_id=user_id
                )
            else:
                await self.twitch_service.setup_chat(twitch, user_id=user_id)

            try:
                await self.twitch_service.setup_eventsub(twitch, twitch_user_id)
            except EventSubError:
                pass
            except Exception as e:
                print(f"Error al iniciar EventSub: {e}")

            await set_running(user_id, True)
            settings = await load_effective_settings(user_id)
            service_mode = str(settings.get("service_mode") or "manual").lower()
            if service_mode == "hybrid":
                await arm(user_id)
                await register_activity_and_monitor(user_id)
            else:
                await stop_monitor(user_id)
        except Exception as e:
            print(f"Error al iniciar servicios: {e}")
