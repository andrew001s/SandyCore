from app.adapters.kick_services import KickService
from app.adapters.twitch_services import TwitchService
from app.adapters.youtube_services import YouTubeService
from app.domain.exceptions import EventSubError
from app.services.kick.lifecycle import set_running as set_kick_running
from app.services.twitch.lifecycle import set_running as set_twitch_running
from app.services.storage.supabase_store import get_kick_tokens, get_twitch_tokens
from app.services.youtube.auth.auth import get_tokens as get_youtube_tokens


class StartServicesCase:
    def __init__(
        self,
        twitch_service: TwitchService | None = None,
        kick_service: KickService | None = None,
        youtube_service: YouTubeService | None = None,
    ):
        self.twitch_service = twitch_service or TwitchService()
        self.kick_service = kick_service or KickService()
        self.youtube_service = youtube_service or YouTubeService()

    async def execute(self, user_id: str, bot: bool = False) -> dict[str, bool]:
        """Arranca los servicios en las plataformas que el usuario tenga conectadas."""
        started_platforms = {"twitch": False, "kick": False, "youtube": False}

        # 1. Twitch (si el usuario tiene credenciales conectadas)
        try:
            twitch_tokens = await get_twitch_tokens(user_id, bot)
            if twitch_tokens:
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
                    await self.twitch_service.setup_eventsub(twitch, user_id, twitch_user_id)
                except EventSubError:
                    pass
                except Exception as exc:
                    print(f"[TWITCH START] EventSub no arrancó: {repr(exc)}")

                started_platforms["twitch"] = True
                print(f"[SERVICES START] Twitch iniciado para {user_id}")
            else:
                print(f"[SERVICES START] Twitch no conectado para {user_id}, omitiendo.")
        except Exception as exc:
            print(f"[SERVICES START] Error al iniciar Twitch para {user_id}: {repr(exc)}")

        # 2. Kick (si el usuario tiene credenciales conectadas)
        try:
            kick_tokens = await get_kick_tokens(user_id, bot)
            if kick_tokens:
                await self.kick_service.return_instance(bot, user_id)
                try:
                    await self.kick_service.subscribe_chat_events(user_id, bot)
                    print(f"[SERVICES START] Kick webhook de eventos verificado/suscrito para {user_id}")
                except Exception as exc:
                    print(f"[SERVICES START] No se pudo verificar la suscripción de Kick para {user_id}: {repr(exc)}")
                await set_kick_running(user_id, True)
                started_platforms["kick"] = True
                print(f"[SERVICES START] Kick iniciado para {user_id}")
            else:
                print(f"[SERVICES START] Kick no conectado para {user_id}, omitiendo.")
        except Exception as exc:
            print(f"[SERVICES START] Error al iniciar Kick para {user_id}: {repr(exc)}")

        # 3. YouTube (si el usuario tiene credenciales conectadas)
        try:
            youtube_tokens = await get_youtube_tokens(user_id)
            if youtube_tokens:
                try:
                    await self.youtube_service.start_services(user_id)
                    started_platforms["youtube"] = True
                    print(f"[SERVICES START] YouTube iniciado para {user_id}")
                except Exception as exc:
                    print(f"[SERVICES START] YouTube no pudo conectar chat en vivo: {repr(exc)}")
            else:
                print(f"[SERVICES START] YouTube no conectado para {user_id}, omitiendo.")
        except Exception as exc:
            print(f"[SERVICES START] Error al iniciar YouTube para {user_id}: {repr(exc)}")

        # Marca el servicio de VTuber como activo a nivel global para el usuario
        await set_twitch_running(user_id, True)
        return started_platforms
