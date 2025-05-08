import json
import os
from twitchAPI.type import AuthScope
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.helper import first
from app.core.config import config

TOKEN_FILE = 'tokens.json'
BOT_TOKEN_FILE = 'bot_tokens.json'

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

twitch = None
user = None
twitch_bot = None
user_bot = None

async def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

async def save_tokens(token, refresh_token):
    with open(TOKEN_FILE, 'w') as f:
        json.dump({'token': token, 'refresh_token': refresh_token}, f)

async def load_bot_tokens():
    if os.path.exists(BOT_TOKEN_FILE):
        with open(BOT_TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

async def save_bot_tokens(token, refresh_token):
    with open(BOT_TOKEN_FILE, 'w') as f:
        json.dump({'token': token, 'refresh_token': refresh_token}, f)
        
async def refresh_access_token(twitch, refresh_token):
    token_data = await twitch.refresh_user_authentication(refresh_token)
    return token_data['access_token'], token_data['refresh_token']

async def create_twitch_instance(bot: bool = False):
    global twitch
    global user

    twitch_client = await Twitch(config.ID, config.SECRET)
    tokens = await load_tokens()
    
    if tokens:
        token = tokens['token']
        refresh_token = tokens['refresh_token']
        try:
            await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
        except:
            token, refresh_token = await refresh_access_token(twitch_client, refresh_token)
            await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
        print("Token cargado para la cuenta principal.")
    else:
        auth = UserAuthenticator(twitch_client, USER_SCOPE, force_verify=True)
        token, refresh_token = await auth.authenticate()
        await save_tokens(token, refresh_token)
        await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
        print("Nuevo token generado y guardado para la cuenta principal.")

    if bot:
        bot_twitch_client = await Twitch(config.ID, config.SECRET)
        bot_tokens = await load_bot_tokens()  # Carga los tokens del archivo específico del bot
        if bot_tokens:
            bot_token = bot_tokens['token']
            bot_refresh_token = bot_tokens['refresh_token']
            try:
                await bot_twitch_client.set_user_authentication(bot_token, USER_SCOPE, bot_refresh_token)
            except:
                bot_token, bot_refresh_token = await refresh_access_token(bot_twitch_client, bot_refresh_token)
                await bot_twitch_client.set_user_authentication(bot_token, USER_SCOPE, bot_refresh_token)
            print("Token cargado para la cuenta bot.")
        else:
            bot_auth = UserAuthenticator(bot_twitch_client, USER_SCOPE, force_verify=True)
            bot_token, bot_refresh_token = await bot_auth.authenticate()
            await save_bot_tokens(bot_token, bot_refresh_token)  # Guarda los tokens en el archivo específico del bot
            await bot_twitch_client.set_user_authentication(bot_token, USER_SCOPE, bot_refresh_token)
            print("Nuevo token generado y guardado para la cuenta bot.")
    user = await first(twitch_client.get_users(logins=[config.CHANNEL]))
    twitch = twitch_client
    if bot:
        twitch_bot = bot_twitch_client
        user_bot = await first(twitch_bot.get_users(logins=[config.TWITCH_BOT_ACCOUNT]))
        return twitch,twitch_bot, user.id
    else:
        return twitch,twitch, user.id


async def close_twitch():
    global twitch
    global twitch_bot
    if twitch:
        await twitch.close()
    if twitch_bot:
        await twitch_bot.close()
    twitch = None
    twitch_bot = None
