import twitchAPI.type as type
from twitchAPI.eventsub.websocket import EventSubWebsocket
import twitchAPI.object.eventsub as eventsub
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
from app.services.gemini import response_gemini_events, response_gemini_rewards
from app.services.voice import play_audio

eventsubInstance = None


async def setup_eventsub(twitch, user_id):
    global eventsubInstance
    eventsubInstance = EventSubWebsocket(twitch)
    eventsubInstance.start()
    await eventsubInstance.listen_channel_points_custom_reward_redemption_add(
        broadcaster_user_id=user_id, callback=chanel_points
    )
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
    print(f"Redemption: {redemtion} from {user}")
    redemtion_obj = '{"user": "' + user + '", "reward": "' + redemtion + '"}'
    response = response_gemini_rewards(redemtion_obj)
    # print("response", response)
    play_audio(response)


async def on_follow(data: eventsub.ChannelFollowEvent):
    user = data.event.user_name
    response = response_gemini_events(f"Follow: nombre_usuario:{user}")
    play_audio(response)


async def on_subscribe(data: eventsub.ChannelSubscribeEvent):
    user = data.event.user_name
    sub = f"Subscribe user: {user}"
    response = response_gemini_events(f"{sub}")
    play_audio(response)


async def on_subscribe_message(data: eventsub.ChannelSubscriptionMessageEvent):
    user = data.event.user_name
    sub = f"Suscribe user: {user} message: {data.event.message}"
    response = response_gemini_events(f"{sub}")
    play_audio(response)


async def on_sub_gift(data: eventsub.ChannelSubscriptionGiftEvent):
    user = data.event.user_name
    gift = f"gift_Sub user: {user}"
    response = response_gemini_events(f"{gift}")
    play_audio(response)


async def on_cheer(data: eventsub.ChannelCheerEvent):
    user = data.event.user_name
    cheer = data.event.message
    cheer_amount = data.event.bits
    cheer = f"cheer user: {user} bits_amount: {cheer_amount} message: {cheer}"
    response = response_gemini_events(f"{cheer}")
    play_audio(response)


async def on_raid(data: eventsub.ChannelRaidEvent):
    user = data.event.from_broadcaster_user_name
    raid = f"Raid: user que raideo: {user}"
    response = response_gemini_events(f"{raid}")
    play_audio(response)


async def close_eventsub():
    global eventsubInstance
    await eventsubInstance.stop()
