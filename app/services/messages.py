from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage
from app.services.gemini import check_message,response_sandy
from app.core.config import config
from app.services.moderator import check_banned_words
from app.services.voice import play_audio
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

chat_instance = None
twitch_instance = None
user_id = None
bot_id = None
chunk_size = 2
chunk_message = []

async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    global chat_instance
    if check_banned_words(msg.text):
        response = check_message(msg.text)
        if response == "NO PERMITIDOS\n":
            await twitch_instance.delete_chat_message(user_id, bot_id, msg.id)
            await chat_instance.send_message(
                msg.room.name,
                f"HEY! {msg.user.name} tu mensaje no es permitido, por favor no lo vuelvas a enviar elshan1Nojao ",
            )
            msg.text = "Mensaje no permitido"
    chunk_message.append(f"{msg.user.name}: {msg.text}")
    if len(chunk_message) >= chunk_size:
        message_str=",".join(chunk_message)
        response = response_sandy(message_str)
        play_audio(response)
        chunk_message.clear()
        
async def run_bot():
    global chat_instance
    global twitch_instance
    global user_id
    global bot_id
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE, force_verify=True)
    token, refresh_token = await auth.authenticate()
    user = await first(twitch.get_users(logins=[TARGET_CHANNEL]))
    bot = await first(twitch.get_users(logins=["lasandybot"]))
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
