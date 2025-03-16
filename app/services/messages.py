from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage
from google import genai
from app.core.config import config
from app.services.moderator import check_banned_words

APP_ID = config.ID
APP_SECRET = config.SECRET
USER_SCOPE = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT,
    AuthScope.CHANNEL_MODERATE,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES,
    AuthScope.MODERATOR_READ_CHAT_MESSAGES,
    AuthScope.MODERATION_READ,
]
TARGET_CHANNEL = config.CHANNEL
REDIRECT_URI = config.REDIRECT
GEMINI_API_KEY = config.GEMINI_API_KEY
PROMPT_MOD = """
        ACTÚA COMO UN MODERADOR DE CHAT INTELIGENTE. CLASIFICA LOS MENSAJES EN "OFENSIVOS" Y "NO OFENSIVOS".
        Expresiones comunes y exclamaciones como "¡Qué verga!" o "¡Mierda!" no son ofensivas si se usan como expresión de asombro.
        Humor y dinámicas de juego como "Jajajajaja, el pendejo el pendejo" o "que pendejo es" no son ofensivas si forman parte de un chiste o dinámica,
        siempre y cuando no haya mala intención.
        Chistes de humor negro o comentarios con bromas racistas, xenofóbicas, etc., no son ofensivos si no atacan a una persona o grupo directamente.
        Comentarios ofensivos claros incluyen ataques directos con odio, insultos, o malintenciones hacia individuos o grupos.
        RESPONDE SOLO "OFENSIVO" O "NO OFENSIVO", ek mensaje es el siguiente:.
    """
chat_instance = None
twitch_instance = None
user_id = None
bot_id=None


async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    global chat_instance
    print(f"in {msg.room.name}, {msg.user.name} said: {msg.text}")
    if check_banned_words(msg.text):
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=PROMPT_MOD + msg.text
        )
        if response.text=="OFENSIVO\n":
            await twitch_instance.delete_chat_message(user_id, bot_id, msg.id)
            await chat_instance.send_message(msg.room.name, f"HEY! {msg.user.name} ¡Eso no se dice! ¡No seas grosero!")


async def run_bot():
    global chat_instance
    global twitch_instance
    global user_id
    global bot_id
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)
    token, refresh_token = await auth.authenticate()
    user = await first(twitch.get_users(logins=[TARGET_CHANNEL]))
    bot = await first(twitch.get_users(logins=['lasandybot']))
    bot_id = bot.id
    user_id = user.id
    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    twitch_instance = twitch
    chat_instance = await Chat(twitch)
    chat_instance.register_event(ChatEvent.READY, on_ready)
    chat_instance.register_event(ChatEvent.MESSAGE, on_message)

    chat_instance.start()

    try:
        input("press ENTER to stop\n")
    finally:
        chat_instance.stop()
        await twitch.close()
