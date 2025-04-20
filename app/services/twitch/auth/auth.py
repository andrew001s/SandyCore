import json
import os
from twitchAPI.type import AuthScope
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.helper import first
from app.core.config import config

TOKEN_FILE = 'tokens.json'

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

async def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

async def save_tokens(token, refresh_token):
    with open(TOKEN_FILE, 'w') as f:
        json.dump({'token': token, 'refresh_token': refresh_token}, f)
        
async def refresh_access_token(twitch, refresh_token):
    token_data = await twitch.refresh_user_authentication(refresh_token)
    return token_data['access_token'], token_data['refresh_token']

async def create_twitch_instance():
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
        print("Token cargado.")
    else:
        auth = UserAuthenticator(twitch_client, USER_SCOPE, force_verify=True)
        token, refresh_token = await auth.authenticate()
        await save_tokens(token, refresh_token)
        await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
        print("Nuevo token generado y guardado.")

    user = await first(twitch_client.get_users(logins=[config.CHANNEL]))
    twitch = twitch_client
    return twitch, user.id
