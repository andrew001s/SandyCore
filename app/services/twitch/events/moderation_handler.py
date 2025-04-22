from app.services.twitch.auth.auth import twitch,user
from app.services.twitch.chat.chat_handler import chat
import json

async def moderator_actions(title: str, name: str):
   try:
      match (name):
         case "title":
            await change_title(title)
         case "game" | "category":
            await change_game(title)
         case "clip":
            await create_clip()
         case "only_followers":
            await only_followers(title)
         case "only_subs":
            await only_subs(title)
         case "only_emotes":
            await only_emotes(title)
         case "slow":
            await slow_mode(title)
         case _:
            await chat.send_message(
               room=user.display_name,
               text=f"POLICE No se ha podido ejecutar la orden POLICE "
            )
            return False
   except Exception as e:
      print(f"Error: {e}")
      return False

async def change_title(title: str):
   await twitch.modify_channel_information(user.id, title=title)
   await chat.send_message(
      room=user.display_name,
      text=f"POLICE Se ha cambiado el titulo del stream a {title} POLICE "
   )
   
async def change_game(game: str):
   game_id = None
   async for g in twitch.get_games(names=[game]):
      game_id = g.id
      break 
   await twitch.modify_channel_information(user.id, game_id)
   await chat.send_message(
      room=user.display_name,
      text=f"POLICE Se ha cambiado la categoria del stream a {game} POLICE "
   )

async def create_clip():
   clip = await twitch.create_clip(user.id)
   await chat.send_message(
      room=user.display_name,
      text=f"POLICE Se ha creado un clip {clip.edit_url} POLICE "
   )

async def only_followers(activate:str):
   if activate=='on':
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,follower_mode=True)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha activado el modo seguidores POLICE "
      )
   else:
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,follower_mode=False)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha desactivado el modo seguidores POLICE "
      )

async def only_subs(activate:str):
   if activate=='on':
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,subscriber_mode=True)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha activado el modo subs POLICE "
      )
   else:
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,subscriber_mode=False)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha desactivado el modo subs POLICE "
      )

async def only_emotes(activate:str):
   if activate=='on':
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,emote_mode=True)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha activado el modo emotes POLICE "
      )
   else:
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,emote_mode=False)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha desactivado el modo emotes POLICE "
      )

async def slow_mode(activate:str):
   if activate=='on':
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,slow_mode=True)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha activado el modo lento POLICE "
      )
   else:
      await twitch.update_chat_settings(broadcaster_id=user.id, moderator_id=user.id,slow_mode=False)
      await chat.send_message(
         room=user.display_name,
         text=f"POLICE Se ha desactivado el modo lento POLICE "
      )
      
async def get_stream_info():
   get_chatters = await twitch.get_chatters(broadcaster_id=user.id, moderator_id=user.id)
   chatters_names = [chatter.user_name for chatter in get_chatters.data if chatter.user_name]
   get_viewers_accounts = len(chatters_names)
   get_stream = await twitch.get_channel_information(broadcaster_id=user.id)
   stream_info = {
      "name": get_stream[0].broadcaster_name,
      "game": get_stream[0].game_name,
      "chatters": chatters_names,
      "title": get_stream[0].title,
      "viewers": get_viewers_accounts,
      "language": get_stream[0].broadcaster_language,
      "tags": get_stream[0].tags,
   }
   stream_info_json = json.dumps(stream_info)
   return stream_info_json
   
   

      
      