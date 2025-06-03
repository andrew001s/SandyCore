import json
import os

import aiohttp
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, UnauthorizedException

from app.core.config import config

TOKEN_FILE = "tokens.json"
BOT_TOKEN_FILE = "bot_tokens.json"

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
    AuthScope.BITS_READ,
]

twitch = None
user = None
twitch_bot = None
user_bot = None


async def refresh_access_token(refresh_token: str):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config.ID,
        "client_secret": config.SECRET,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(
                    f"Failed to refresh token: {resp.status} {await resp.text()}"
                )
            return await resp.json()


async def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


async def save_tokens(token, refresh_token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "refresh_token": refresh_token}, f)


async def load_bot_tokens():
    if os.path.exists(BOT_TOKEN_FILE):
        with open(BOT_TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


async def save_bot_tokens(token, refresh_token):
    with open(BOT_TOKEN_FILE, "w") as f:
        json.dump({"token": token, "refresh_token": refresh_token}, f)


async def get_tokens(bot: bool = False):
    if bot:
        tokens = await load_bot_tokens()
    else:
        tokens = await load_tokens()
    if tokens:
        return tokens
    return None, None


async def create_twitch_instance(
    bot: bool = False, token: str = None, refresh_token: str = None
):
    global twitch
    global user
    global user_bot
    global twitch_bot
    try:
        if bot:
            twitch_bot = await authenticate_twitch(token, refresh_token)
            user_bot = await get_profile_users(bot=True)
            return twitch, twitch_bot, user_bot.id
        else:
            twitch = await authenticate_twitch(token, refresh_token)
            user = await get_profile_users(bot=False)
            return twitch, twitch, user.id
    except Exception as e:
        raise Exception(f"Error al crear la instancia de Twitch: {str(e)}")


async def authenticate_twitch(token: str = None, refresh_token: str = None):
    twitch_client = await Twitch(config.ID, config.SECRET)
    try:
        # Intentamos setear el token actual
        await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
    except UnauthorizedException:
        # Token vencido o inválido -> refrescamos
        print("Token vencido. Renovando...")
        new_tokens = await refresh_access_token(refresh_token)
        token = new_tokens["access_token"]
        refresh_token = new_tokens["refresh_token"]
        await save_tokens(token, refresh_token)  # Guarda los nuevos tokens
        await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
    return twitch_client


async def get_profile_users(bot: bool = False):
    global twitch
    global twitch_bot
    global user_bot
    global user
    if bot:
        user_bot = await first(twitch_bot.get_users())
        return user_bot
    else:
        user = await first(twitch.get_users())
        return user


async def return_twitch_instance(bot: bool = False):
    global twitch
    global twitch_bot
    global user
    global user_bot
    if bot:
        return twitch, twitch_bot, user.id
    else:
        return twitch, twitch, user.id


async def close_twitch():
    global twitch
    global twitch_bot
    if twitch:
        await twitch.close()
    if twitch_bot:
        await twitch_bot.close()
    twitch = None
    twitch_bot = None
