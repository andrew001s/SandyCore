import app.services.kick.auth.auth as auth
from app.services.kick.lifecycle import stop_services


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


async def logout_kick(user_id=None):
    print(f"[KICK SERVICE] logout_kick() -> detener servicios y eliminar tokens para {user_id}")
    from app.services.storage.supabase_store import delete_kick_tokens
    try:
        await stop_services(user_id)
    except Exception as exc:
        print(f"[KICK SERVICE] Error al detener servicios en logout: {repr(exc)}")
    await auth.close_kick(user_id)
    if user_id:
        await delete_kick_tokens(user_id)

