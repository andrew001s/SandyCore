import app.services.twitch.auth.auth as auth
from app.services.twitch.chat.chat_handler import close_chat, setup_chat
from app.services.twitch.events.eventsub_handler import close_eventsub, setup_eventsub
from app.services.twitch.lifecycle import stop_services


async def get_user_profile(bot=False, user_id=None) -> dict:
    try:
        user = await auth.get_profile_users(bot, user_id)
        if user is None:
            raise Exception("Usuario no autenticado")
        return user
    except Exception as e:
        raise Exception(f"Error al obtener el perfil: {str(e)}")


async def close_twitch(user_id=None):
    print("[TWITCH SERVICE] close_twitch() -> stop runtime")
    await stop_services(user_id)


async def logout_twitch(user_id=None):
    print(f"[TWITCH SERVICE] logout_twitch() -> detener chat/eventsub y eliminar tokens para {user_id}")
    from app.services.storage.supabase_store import delete_twitch_tokens
    # 1. Detener chat y eventsub directamente (sin alterar el estado global de ejecución)
    try:
        await close_chat_instance(user_id)
        await close_eventsub(user_id)
    except Exception as exc:
        print(f"[TWITCH SERVICE] Error al detener chat/eventsub en logout: {repr(exc)}")
    # 2. Cerrar sesiones en memoria
    await auth.close_twitch(user_id)
    # 3. Eliminar tokens de Supabase
    if user_id:
        await delete_twitch_tokens(user_id)


async def start_bot(user_id=None):
    await close_chat_instance(user_id)
    await close_eventsub(user_id)


async def close_chat_instance(user_id=None):
    await close_chat(user_id)


async def setup_chat_instance(twitch_obj, twitch_bot=None, user_id=None):
    await setup_chat(twitch_obj, twitch_bot, user_id)


async def setup_eventsub_instance(twitch, user_id, broadcaster_id=None):
    try:
        await setup_eventsub(twitch, user_id, broadcaster_id)
    except Exception as e:
        raise Exception(f"Error al iniciar EventSub: {str(e)}")
