from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage
from app.services.gemini import check_message,response_sandy,response_gemini_rewards,response_gemini_events
from app.core.config import config
from app.services.moderator import check_banned_words
from app.services.voice import play_audio
from twitchAPI.pubsub import PubSub
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelFollowEvent,ChannelSubscribeEvent,ChannelSubscriptionMessageEvent,ChannelSubscriptionGiftEvent, ChannelCheerEvent, ChannelRaidEvent

APP_ID = config.ID
APP_SECRET = config.SECRET
USER_SCOPE = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT,
    AuthScope.CHANNEL_MODERATE,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES,
    AuthScope.MODERATOR_READ_CHAT_MESSAGES,
    AuthScope.MODERATION_READ,
    AuthScope.CHANNEL_READ_REDEMPTIONS,
    AuthScope.CHANNEL_MANAGE_REDEMPTIONS,
    AuthScope.CHANNEL_MANAGE_BROADCAST,
    AuthScope.USER_BOT,
    AuthScope.USER_WRITE_CHAT,
    AuthScope.CHANNEL_BOT,
    AuthScope.CLIPS_EDIT,
    AuthScope.USER_READ_EMAIL,
    AuthScope.MODERATOR_MANAGE_CHAT_SETTINGS,
    AuthScope.MODERATOR_READ_CHATTERS,
    AuthScope.MODERATOR_READ_FOLLOWERS,
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.BITS_READ
]
TARGET_CHANNEL = config.CHANNEL
REDIRECT_URI = config.REDIRECT
BOT_ACCOUNT = config.TWITCH_BOT_ACCOUNT
chat_instance = None
twitch_instance = None
user_id = None
bot_id = None
chunk_size = 3
chunk_message = []

async def on_ready(ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(TARGET_CHANNEL)


async def on_message(msg: ChatMessage):
    global chat_instance
 
    if check_banned_words(msg.text) and msg.user.mod is False:
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

async def chanel_points(uuid: str, msg: dict):
    redemtion=msg['data']['redemption']['reward']['title']
    if redemtion != "Te mando un saludo" and redemtion!= "Sound Alert: Screamer" and redemtion!="Me gusta el directo":
        return
    user=msg["data"]['redemption']['user']['display_name']
    print(f"Redemption: {redemtion} from {user}")
    redemtion_obj='{"user": "'+user+'", "reward": "'+redemtion+'"}'
    response = response_gemini_rewards(redemtion_obj)
    play_audio(response)

async def on_follow(data: ChannelFollowEvent):
    user = data.event.user_name
    response = response_gemini_events(f"Follow: nombre_usuario:{user}")
    play_audio(response)
    
async def on_subscribe(data: ChannelSubscribeEvent):
    user=data.event.user_name
    sub=f"Subscribe user: {user}"
    response = response_gemini_events(f"{sub}")
    play_audio(response)

async def on_subscribe_message(data: ChannelSubscriptionMessageEvent):
    user=data.event.user_name
    sub=f"Suscribe user: {user} message: {data.event.message}"
    response = response_gemini_events(f"{sub}")
    play_audio(response)
    
async def on_sub_gift(data: ChannelSubscriptionGiftEvent):
    user=data.event.user_name
    gift=f"gift_Sub user: {user}"
    response = response_gemini_events(f"{gift}")
    play_audio(response)
    
async def on_cheer(data:ChannelCheerEvent):
    user=data.event.user_name
    cheer=data.event.message
    cheer_amount=data.event.bits
    cheer=f"cheer user: {user} bits_amount: {cheer_amount} message: {cheer}"
    response = response_gemini_events(f"{cheer}")

async def on_raid(data:ChannelRaidEvent):
    user=data.event.from_broadcaster_user_name
    raid=f"Raid: user que raideo: {user}"
    response = response_gemini_events(f"{raid}")
    play_audio(response)

async def run_bot():
    global chat_instance
    global twitch_instance
    global user_id
    global bot_id
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE, force_verify=True)
    token, refresh_token = await auth.authenticate()
    user = await first(twitch.get_users(logins=[TARGET_CHANNEL]))
    bot = await first(twitch.get_users(logins=[BOT_ACCOUNT]))
    bot_id = bot.id
    user_id = user.id
    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    twitch_instance = twitch
    chat_instance = await Chat(twitch)
    chat_instance.register_event(ChatEvent.READY, on_ready)
    chat_instance.register_event(ChatEvent.MESSAGE, on_message)
    pubsun = PubSub(twitch)
    eventsub=EventSubWebsocket(twitch)
    eventsub.start()
    await eventsub.listen_channel_follow_v2(user_id,bot_id, on_follow)
    await eventsub.listen_channel_subscribe(user_id,on_subscribe)
    await eventsub.listen_channel_subscription_message(user_id,on_subscribe_message)
    await eventsub.listen_channel_subscription_gift(user_id,on_sub_gift)
    await eventsub.listen_channel_cheer(user_id,on_cheer)
    await eventsub.listen_channel_raid(to_broadcaster_user_id=user_id,callback=on_raid)
    await pubsun.listen_channel_points(user_id,chanel_points)
    pubsun.start()  
    chat_instance.start()
    try:
        input("press ENTER to stop\n")
    except KeyboardInterrupt:
        pass
    finally:
        await eventsub.stop()
        await pubsun.stop()
        await chat_instance.stop()
        await twitch.close()
