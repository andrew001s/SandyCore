from app.adapters.kick_services import KickService
from app.adapters.twitch_services import TwitchService
from app.adapters.youtube_services import YouTubeService
from app.services.kick.lifecycle import is_running as is_kick_running
from app.services.kick.lifecycle import stop_services as stop_kick_services
from app.services.twitch.lifecycle import stop_services as stop_twitch_services


class StopServicesUseCase:
    def __init__(
        self,
        twitch_service: TwitchService | None = None,
        kick_service: KickService | None = None,
        youtube_service: YouTubeService | None = None,
    ):
        self.twitch_service = twitch_service or TwitchService()
        self.kick_service = kick_service or KickService()
        self.youtube_service = youtube_service or YouTubeService()

    async def execute(self, user_id: str | None = None) -> dict[str, bool]:
        print(f"[SERVICES STOP] Pausando servicios para user_id={user_id}")
        stopped = {"twitch": False, "kick": False, "youtube": False}

        # 1. Twitch (detiene chat y eventsub sin cerrar sesión de autenticación ni borrar tokens)
        try:
            await stop_twitch_services(user_id)
            stopped["twitch"] = True
        except Exception as exc:
            print(f"[SERVICES STOP] Error al detener Twitch para {user_id}: {repr(exc)}")

        # 2. Kick
        try:
            if is_kick_running(user_id):
                await stop_kick_services(user_id)
                stopped["kick"] = True
        except Exception as exc:
            print(f"[SERVICES STOP] Error al detener Kick para {user_id}: {repr(exc)}")

        # 3. YouTube
        try:
            await self.youtube_service.stop_services(user_id)
            stopped["youtube"] = True
        except Exception as exc:
            print(f"[SERVICES STOP] Error al detener YouTube para {user_id}: {repr(exc)}")

        return stopped
