from app.adapters.kick_services import KickService
from app.services.kick.lifecycle import set_running


class StartKickServicesCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str, bot: bool = False):
        try:
            kick, kick_bot, kick_user_id = await self.kick_service.return_instance(
                bot, user_id
            )
            await set_running(user_id, True)
        except Exception as e:
            print(f"Error al iniciar servicios de Kick: {e}")
