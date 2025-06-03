import app.services.twitch.auth.auth as auth
from app.services.twitch.chat.chat_handler import close_chat
from app.services.twitch.events.eventsub_handler import close_eventsub


async def get_user_profile(bot=False) -> dict:
    try:
        user = auth.user_bot if bot else auth.user
        if user is None:
            raise Exception("Usuario no autenticado")
        return user
    except Exception as e:
        raise Exception(f"Error al obtener el perfil: {str(e)}")


async def close_twitch():
    await auth.close_twitch()
    await close_chat_instance()
    await close_eventsub()


async def start_bot():
    await close_chat_instance()
    await close_eventsub()


async def close_chat_instance():
    await close_chat()
