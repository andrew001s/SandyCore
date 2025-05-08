import app.services.twitch.auth.auth as auth
from app.services.twitch.chat.chat_handler import setup_chat
from app.services.twitch.events.eventsub_handler import setup_eventsub
from app.models.ProfileModel import ProfileModel


async def run_bot(bot: bool = False):
    twitch, twitch_bot, user_id = await auth.create_twitch_instance(bot)
    if bot:
        await setup_chat(twitch_bot)
    else:
        await setup_chat(twitch)
    await setup_eventsub(twitch, user_id)


async def get_user_profile() -> dict:
    user = auth.user
    profile = ProfileModel(
        id=user.id,
        username=user.display_name,
        email=user.email,
        picProfile=user.profile_image_url,
    )
    return profile.model_dump() 
