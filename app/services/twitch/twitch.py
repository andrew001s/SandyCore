import app.services.twitch.auth.auth as auth
from app.services.twitch.chat.chat_handler import setup_chat
from app.services.twitch.events.eventsub_handler import setup_eventsub

async def run_bot():
    twitch, user_id = await auth.create_twitch_instance()
    await setup_chat(twitch)
    await setup_eventsub(twitch, user_id)

