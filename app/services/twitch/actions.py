from app.services.twitch.twitch import twitch_instance,user_id,bot_id

async def moderator_actions(title: str,name: str):
   match (name):
      case "title":
         await change_title(title)
      case "game" | "category":
         await change_game(title)
   

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
   print(game_id)
   await twitch_instance.modify_channel_information(user_id, game_id)
   await twitch_instance.send_chat_message(
      broadcaster_id=user_id,
      sender_id=bot_id,
      message=f"POLICE Se ha cambiado la categoria del stream a {game} POLICE "
   )