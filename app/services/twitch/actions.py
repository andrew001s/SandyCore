from app.services.twitch.twitch import twitch_instance,user_id,bot_id

async def moderator_actions(title: str,name: str):
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
         await twitch_instance.send_chat_message(
            broadcaster_id=user_id,
            sender_id=bot_id,
            message=f"POLICE No se ha podido ejecutar la orden POLICE "
         )
         return False
         


   

async def change_title(title: str):
   await twitch_instance.modify_channel_information(user_id, title=title)
   await twitch_instance.send_chat_message(
      broadcaster_id=user_id,
      sender_id=bot_id,
      message=f"POLICE Se ha cambiado el titulo del stream a {title} POLICE "
   )
   
async def change_game(game: str):
   game_id = None
   async for g in twitch_instance.get_games(names=[game]):
      game_id = g.id
      break 
   await twitch_instance.modify_channel_information(user_id, game_id)
   await twitch_instance.send_chat_message(
      broadcaster_id=user_id,
      sender_id=bot_id,
      message=f"POLICE Se ha cambiado la categoria del stream a {game} POLICE "
   )

async def create_clip():
   clip = await twitch_instance.create_clip(user_id)
   await twitch_instance.send_chat_message(
      broadcaster_id=user_id,
      sender_id=bot_id,
      message=f"POLICE Se ha creado un clip {clip.edit_url} POLICE "
   )

async def only_followers(activate:str):
   if activate=='on':
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,follower_mode=True)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha activado el modo seguidores POLICE "
      )
   else:
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,follower_mode=False)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha desactivado el modo seguidores POLICE "
      )

async def only_subs(activate:str):
   if activate=='on':
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,subscriber_mode=True)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha activado el modo subs POLICE "
      )
   else:
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,subscriber_mode=False)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha desactivado el modo subs POLICE "
      )

async def only_emotes(activate:str):
   if activate=='on':
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,emote_mode=True)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha activado el modo emotes POLICE "
      )
   else:
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,emote_mode=False)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha desactivado el modo emotes POLICE "
      )

async def slow_mode(activate:str):
   if activate=='on':
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,slow_mode=True)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha activado el modo lento POLICE "
      )
   else:
      await twitch_instance.update_chat_settings(broadcaster_id=user_id, moderator_id=bot_id,slow_mode=False)
      await twitch_instance.send_chat_message(
         broadcaster_id=user_id,
         sender_id=bot_id,
         message=f"POLICE Se ha desactivado el modo lento POLICE "
      )