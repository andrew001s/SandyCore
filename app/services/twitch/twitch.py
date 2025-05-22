import app.services.twitch.auth.auth as auth
import twitchAPI.type as type
from app.services.twitch.chat.chat_handler import setup_chat, close_chat
from app.services.twitch.events.eventsub_handler import setup_eventsub, close_eventsub
from app.models.ProfileModel import ProfileModel

async def get_user_profile(bot=False) -> dict:
    if not bot:
        user = auth.user
        profile = ProfileModel(
            id=user.id,
            username=user.display_name,
            email=user.email,
            picProfile=user.profile_image_url,
        )
        return profile.model_dump() 
    else:
        user = auth.user_bot
        profile = ProfileModel(
            id=user.id,
            username=user.display_name,
            email=user.email,
            picProfile=user.profile_image_url,
        )
        return profile.model_dump()

async def close_twitch():
    await auth.close_twitch()
    await close_chat_instance()
    await close_eventsub()
    
async def close_chat_instance():
    await close_chat()