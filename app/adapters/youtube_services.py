from app.models.youtube_models import YouTubeBroadcastUpdateModel


class YouTubeService:
    async def get_profile(self, user_id: str | None = None, bot: bool = False):
        from app.services.youtube.youtube import get_profile_users

        return await get_profile_users(bot, user_id)

    async def get_tokens(self, user_id: str | None = None, bot: bool = False):
        from app.services.youtube.youtube import get_tokens

        return await get_tokens(user_id, bot)

    async def start_auth(
        self,
        user_id: str | None = None,
        redirect_uri: str | None = None,
    ):
        from app.services.youtube.youtube import start_auth

        return await start_auth(user_id, redirect_uri=redirect_uri)

    async def complete_auth(
        self,
        code: str,
        state: str,
        redirect_uri: str | None = None,
    ):
        from app.services.youtube.youtube import complete_auth

        return await complete_auth(code, state, redirect_uri=redirect_uri)

    async def start_services(self, user_id: str | None = None):
        from app.services.youtube.youtube import start_services

        return await start_services(user_id)

    async def stop_services(self, user_id: str | None = None):
        from app.services.youtube.youtube import stop_services

        return await stop_services(user_id)

    async def get_service_status(self, user_id: str | None = None):
        from app.services.youtube.youtube import get_service_status

        return await get_service_status(user_id)

    async def list_broadcasts(self, user_id: str | None = None, broadcast_status: str = "active"):
        from app.services.youtube.youtube import list_broadcasts

        return await list_broadcasts(user_id, broadcast_status)

    async def get_stats(self, user_id: str | None = None):
        from app.services.youtube.youtube import get_stats

        return await get_stats(user_id)

    async def update_broadcast(
        self,
        user_id: str | None = None,
        payload: YouTubeBroadcastUpdateModel | dict | None = None,
    ):
        from app.services.youtube.youtube import update_broadcast

        data = payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump") else (payload or {})
        return await update_broadcast(user_id, data)

    async def send_chat_message(self, user_id: str | None = None, live_chat_id: str | None = None, message: str = ""):
        from app.services.youtube.youtube import send_chat_message

        return await send_chat_message(user_id, live_chat_id, message)

    async def transition_broadcast(
        self,
        user_id: str | None = None,
        broadcast_id: str | None = None,
        status: str = "live",
    ):
        from app.services.youtube.youtube import transition_broadcast

        return await transition_broadcast(user_id, broadcast_id, status)

    async def logout(self, user_id: str | None = None):
        from app.services.youtube.youtube import logout

        return await logout(user_id)
