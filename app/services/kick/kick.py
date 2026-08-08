import app.services.kick.auth.auth as auth
from app.services.kick.lifecycle import disarm, stop_services


async def get_user_profile(bot: bool = False, user_id=None) -> dict:
    try:
        user = await auth.get_profile_users(bot, user_id)
        if user is None:
            raise Exception("Usuario no autenticado")
        return user
    except Exception as e:
        raise Exception(f"Error al obtener el perfil: {str(e)}")


async def close_kick(user_id=None):
    await stop_services(user_id)
    await disarm(user_id)


async def logout_kick(user_id=None):
    await auth.close_kick(user_id)

