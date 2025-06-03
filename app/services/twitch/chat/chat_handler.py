from twitchAPI.chat import Chat, ChatEvent, ChatMessage, EventData

import app.services.twitch.auth.auth as auth
from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.config import config
from app.core.use_cases.chat_use_case import ChatUseCase
from app.services.gemini import check_message, response_sandy
from app.services.moderator import check_banned_words

TARGET_CHANNEL = config.CHANNEL
BOT_CHANNEL = config.TWITCH_BOT_ACCOUNT
chat = None
twitch = None
bots = ["streamlabs", "streamelements", "nightbot", BOT_CHANNEL]
chat_use_case = ChatUseCase(WebsocketAdapter())


async def setup_chat(twitch_instance):
    global chat
    global twitch
    twitch = twitch_instance
    chat = await Chat(twitch)
    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    chat.start()


async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(TARGET_CHANNEL)
    await chat_use_case.notify_chat_connected(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    print(f"{msg.user.name}: {msg.text}")
    if msg.user.name not in bots:
        if check_banned_words(msg.text) and msg.user.mod is False:
            response = check_message(msg.text)
            if response == "NO PERMITIDOS\n":
                await twitch.delete_chat_message(auth.user.id, auth.user.id, msg.id)
                await chat.send_message(
                    msg.room.name,
                    f"HEY! {msg.user.name} tu mensaje no es permitido, por favor no lo vuelvas a enviar elshan1Nojao ",
                )
                msg.text = "Mensaje no permitido"
                return

        message_str = f"{msg.user.name}: {msg.text}"
        response = response_sandy(message_str)
        await chat_use_case.handle_message(msg.user.name, msg.text, response)


async def close_chat():
    global chat
    if chat:
        chat.stop()
        chat = None
