from twitchAPI.chat import Chat, ChatEvent
from twitchAPI.chat import EventData, ChatMessage
from app.core.config import config
from app.services.moderator import check_banned_words
from app.services.gemini import check_message
import app.services.twitch.auth.auth as auth
from app.services.gemini import response_sandy
from app.services.voice import play_audio

TARGET_CHANNEL = config.CHANNEL
BOT_CHANNEL = config.TWITCH_BOT_ACCOUNT
chunk_size = 3
chunk_message = []
chat = None
bots=['streamlabs','streamelements','nightbot',BOT_CHANNEL]

async def setup_chat(twitch):
    global chat
    chat = await Chat(twitch)
    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    chat.start()

async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    print(f"{msg.user.name}: {msg.text}")
    print(f"{msg.user}")
    if msg.user.name not in bots:
        if check_banned_words(msg.text) and msg.user.mod is False:
            response = check_message(msg.text)
            if response == "NO PERMITIDOS\n":
                await auth.twitch.delete_chat_message(auth.user.id, auth.user.id, msg.id)
                await chat.send_message(
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