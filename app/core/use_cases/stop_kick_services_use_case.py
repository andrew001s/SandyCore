from app.adapters.kick_services import KickService
from app.services.kick.lifecycle import stop_services


class StopKickServicesUseCase:
    def __init__(self, kick_service: KickService):
        self.kick_service = kick_service

    async def execute(self, user_id: str | None = None):
        print(f"[KICK STOP] Pausando servicios para user_id={user_id}")
        await stop_services(user_id)
