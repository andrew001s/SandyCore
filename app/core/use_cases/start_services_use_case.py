from app.adapters.twitch_services import TwitchService
from app.domain.exceptions import EventSubError
from app.services.twitch.lifecycle import set_running


class StartServicesCase:
    def __init__(self, twitch_service: TwitchService):
        self.twitch_service = twitch_service

    async def execute(self, user_id: str, bot: bool = False):
        """Arranca chat y EventSub.

        Los fallos se propagan a propósito: antes se capturaban aquí y solo se
        imprimían, así que `/start` devolvía 200 "Servicios iniciados" aunque no
        hubiera arrancado nada y el usuario no tenía forma de enterarse.
        """
        twitch, twitch_bot, twitch_user_id = await self.twitch_service.return_instance(
            bot, user_id
        )
        if bot:
            await self.twitch_service.setup_chat(
                twitch_bot, twitch_bot=twitch, user_id=user_id
            )
        else:
            await self.twitch_service.setup_chat(twitch, user_id=user_id)

        # EventSub sí puede fallar sin tumbar el arranque: el chat funciona igual
        # y las suscripciones se reintentan al volver a iniciar.
        try:
            await self.twitch_service.setup_eventsub(twitch, user_id, twitch_user_id)
        except EventSubError:
            pass
        except Exception as exc:
            print(f"[TWITCH START] EventSub no arrancó: {repr(exc)}")

        await set_running(user_id, True)
