from app.models.kick_profile_model import KickProfileModel


class KickService:
    async def create_instance(
        self,
        user_id: str | None = None,
        token: str = None,
        refresh_token: str = None,
        bot: bool = False,
    ):
        from app.services.kick.auth import auth

        return await auth.create_kick_instance(user_id, bot, token, refresh_token)

    async def get_profile(self, user_id: str | None = None, bot: bool = False):
        from app.services.kick.auth import auth

        user = await auth.get_profile_users(bot, user_id)
        if user is None:
            raise Exception("Usuario no autenticado")

        try:
            profile = KickProfileModel(
                id=str(user.get("id", "")),
                username=str(
                    user.get("username")
                    or user.get("slug")
                    or user.get("name")
                    or ""
                ),
                email=str(user.get("email") or ""),
                picProfile=str(
                    user.get("profile_picture")
                    or user.get("avatar")
                    or user.get("avatar_url")
                    or ""
                ),
                channel_slug=user.get("channel_slug") or user.get("slug"),
                bio=user.get("bio"),
                created_at=user.get("created_at"),
            )
            return profile.model_dump()
        except Exception as e:
            raise Exception(f"Error al mapear el perfil: {str(e)}")

    async def return_instance(self, bot: bool = False):
        from app.services.kick.auth import auth

        return await auth.return_kick_instance(bot)

    async def close_kick(self):
        from app.services.kick.kick import close_kick as close_kick_service

        await close_kick_service()

    async def logout_kick(self):
        from app.services.kick.kick import logout_kick as logout_kick_service

        await logout_kick_service()

    async def get_tokens(self, user_id: str | None = None, bot: bool = False):
        from app.services.kick.auth import auth

        return await auth.get_tokens(user_id, bot)

    async def save_tokens(
        self,
        user_id: str | None = None,
        bot: bool = False,
        token: str = None,
        refresh_token: str = None,
    ):
        from app.services.kick.auth import auth

        return await auth.save_tokens(user_id, token, refresh_token, bot)

    async def subscribe_chat_events(self, user_id: str | None = None, bot: bool = False):
        from app.services.kick.auth import auth

        return await auth.subscribe_chat_message_events(user_id, bot)
