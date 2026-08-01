import twitchAPI.object.eventsub as eventsub
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent

from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.client_settings import load_effective_settings
from app.services.gemini import response_gemini_events, response_gemini_rewards

eventsubInstance = None
ACTIVE_USER_ID = None

eventsubUseCase = EventSubUseCase(WebsocketAdapter())


async def setup_eventsub(twitch, user_id):
    global eventsubInstance
    global ACTIVE_USER_ID
    ACTIVE_USER_ID = user_id
    settings = await load_effective_settings(user_id)
    feature_flags = settings.get("feature_flags") or {}
    if not feature_flags.get("events", True) and not feature_flags.get("rewards", True):
        print("EventSub desactivado por configuración del usuario")
        return

    if eventsubInstance is None:
        eventsubInstance = EventSubWebsocket(twitch)
        eventsubInstance.start()
        if feature_flags.get("rewards", True):
            await eventsubInstance.listen_channel_points_custom_reward_redemption_add(
                broadcaster_user_id=user_id, callback=chanel_points
            )
        if feature_flags.get("events", True):
            await eventsubInstance.listen_channel_follow_v2(user_id, user_id, on_follow)
            await eventsubInstance.listen_channel_subscribe(user_id, on_subscribe)
            await eventsubInstance.listen_channel_subscription_message(
                user_id, on_subscribe_message
            )
            await eventsubInstance.listen_channel_subscription_gift(user_id, on_sub_gift)
            await eventsubInstance.listen_channel_cheer(user_id, on_cheer)
            await eventsubInstance.listen_channel_raid(
                to_broadcaster_user_id=user_id, callback=on_raid
            )


async def chanel_points(msg: ChannelPointsCustomRewardRedemptionAddEvent):
    redemtion = msg.event.reward.title
    if (
        redemtion != "Te mando un saludo"
        and redemtion != "Sound Alert: Screamer"
        and redemtion != "Me gusta el directo"
    ):
        return
    user = msg.event.user_name
    message = f"Redemption: {redemtion} from {user}"
    redemtion_obj = '{"user": "' + user + '", "reward": "' + redemtion + '"}'
    response = await response_gemini_rewards(redemtion_obj, ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", message, response)


async def on_follow(data: eventsub.ChannelFollowEvent):
    user = data.event.user_name
    message = f"Follow nombre_usuario: {user}"
    response = await response_gemini_events(f"{message}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", message, response)


async def on_subscribe(data: eventsub.ChannelSubscribeEvent):
    user = data.event.user_name
    sub = f"Subscribe user: {user}"
    response = await response_gemini_events(f"{sub}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", sub, response)


async def on_subscribe_message(data: eventsub.ChannelSubscriptionMessageEvent):
    user = data.event.user_name
    sub = f"Suscribe user: {user} message: {data.event.message}"
    response = await response_gemini_events(f"{sub}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("speech", sub, response)


async def on_sub_gift(data: eventsub.ChannelSubscriptionGiftEvent):
    user = data.event.user_name
    gift = f"gift_Sub user: {user}"
    response = await response_gemini_events(f"{gift}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", gift, response)


async def on_cheer(data: eventsub.ChannelCheerEvent):
    user = data.event.user_name
    cheer = data.event.message
    cheer_amount = data.event.bits
    cheer = f"cheer user: {user} bits_amount: {cheer_amount} message: {cheer}"
    response = await response_gemini_events(f"{cheer}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", cheer, response)


async def on_raid(data: eventsub.ChannelRaidEvent):
    user = data.event.from_broadcaster_user_name
    raid = f"Raid: user que raideo: {user}"
    response = await response_gemini_events(f"{raid}", ACTIVE_USER_ID)
    await eventsubUseCase.handle_events("reaction", raid, response)


async def close_eventsub():
    global eventsubInstance
    if eventsubInstance is not None:
        await eventsubInstance.stop()
        eventsubInstance = None
