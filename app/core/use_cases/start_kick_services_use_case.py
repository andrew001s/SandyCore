from app.adapters.kick_services import KickService
from app.services.kick.lifecycle import register_activity_and_monitor, stop_monitor, set_running
from app.services.client_settings import load_effective_settings


class StartKickServicesCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str, bot: bool = False):
        try:
            kick, kick_bot, kick_user_id = await self.kick_service.return_instance(bot)
            await set_running(user_id, True)
            settings = await load_effective_settings(user_id)
            service_mode = str(settings.get("service_mode") or "manual").lower()
            if service_mode == "hybrid":
                await register_activity_and_monitor(user_id)
            else:
                await stop_monitor(user_id)
        except Exception as e:
            print(f"Error al iniciar servicios de Kick: {e}")
