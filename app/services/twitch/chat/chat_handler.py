from twitchAPI.chat import Chat, ChatEvent, ChatMessage, EventData

import app.services.twitch.auth.auth as auth
from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.runtime import get_active_user_id
from app.core.use_cases.chat_use_case import ChatUseCase
from app.services.client_settings import load_effective_settings
from app.services.gemini import check_message, response_sandy
from app.services.moderator import check_banned_words

TARGET_CHANNEL = None
BOT_CHANNEL = None
ACTIVE_USER_ID = None
chat = None
twitch = None
twitch_bot_instance = None
bots = ["streamlabs", "streamelements", "nightbot"]
chat_use_case = ChatUseCase(WebsocketAdapter())
chunk_message = []
chunk_size = 1


async def setup_chat(twitch_instance, twitch_bot=None, user_id=None):
    global chat
    global twitch
    global twitch_bot_instance
    global TARGET_CHANNEL
    global BOT_CHANNEL
    global ACTIVE_USER_ID
    global bots

    twitch = twitch_instance
    twitch_bot_instance = twitch_bot if twitch_bot else twitch_instance
    ACTIVE_USER_ID = user_id or get_active_user_id()
    settings = await load_effective_settings(ACTIVE_USER_ID)
    TARGET_CHANNEL = settings.get("twitch_channel")
    BOT_CHANNEL = settings["twitch_bot_account"]
    bots = ["streamlabs", "streamelements", "nightbot", BOT_CHANNEL]

    if not TARGET_CHANNEL:
        raise Exception(
            "Falta twitch_channel en la configuración. "
            "Primero guarda la configuración o vuelve a autenticar Twitch."
        )

    chat = await Chat(twitch)
    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    chat.start()


async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    if not TARGET_CHANNEL:
        raise Exception("No hay canal configurado para unir el chat")
    await ready_event.chat.join_room(TARGET_CHANNEL)
    await chat_use_case.notify_chat_connected(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    global twitch
    global twitch_bot_instance
    global ACTIVE_USER_ID
    print(f"{msg.user.name}: {msg.text}")
    if msg.user.name not in bots:
        if check_banned_words(msg.text) and msg.user.mod is False:
            moderation = await check_message(msg.text, ACTIVE_USER_ID)
            if moderation == "NO PERMITIDOS\n":
                twitch_instance = twitch_bot_instance if twitch_bot_instance else twitch
                await twitch_instance.delete_chat_message(
                    auth.user.id, auth.user.id, msg.id
                )
                await chat.send_message(
                    msg.room.name,
                    f"HEY! {msg.user.name} tu mensaje no es permitido, por favor no lo vuelvas a enviar elshan1Nojao ",
                )
                msg.text = "Mensaje no permitido"
                return
        message_str = f"{msg.user.name}: {msg.text}"
        chunk_message.append(message_str)
        if len(chunk_message) >= chunk_size:
            response = await response_sandy(message_str, ACTIVE_USER_ID)
            await chat_use_case.handle_message(msg.user.name, msg.text, response)
            chunk_message.clear()


async def close_chat():
    global chat
    if chat:
        chat.stop()
        chat = None
