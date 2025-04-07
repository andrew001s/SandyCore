from app.services.twitch.twitch import twitch_instance,user_id

async def moderator_actions(title: str):
   await twitch_instance.modify_channel_information(user_id, title=title)