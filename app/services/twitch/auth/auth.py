import aiohttp
import traceback
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, UnauthorizedException

from app.core.runtime import get_active_user_id, set_active_user_id
from app.services.client_settings import load_effective_settings
from app.services.storage.sqlite_store import get_twitch_tokens, save_twitch_tokens
from app.services.client_settings import save_effective_settings

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


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return owner_id


async def refresh_access_token(user_id: str, refresh_token: str):
    settings = await load_effective_settings(user_id)
    client_id = settings.get("twitch_client_id")
    client_secret = settings.get("twitch_client_secret")
    if not client_id or not client_secret:
        raise Exception(
            "Faltan twitch_client_id o twitch_client_secret en la configuración del usuario"
        )

    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(
                    f"Failed to refresh token: {resp.status} {await resp.text()}"
                )
            return await resp.json()


async def get_tokens(user_id: str | None = None, bot: bool = False):
    owner_id = _resolve_user_id(user_id)
    tokens = await get_twitch_tokens(owner_id, bot)
    if tokens:
        return tokens
    return None


async def save_tokens(
    user_id: str | None = None,
    token: str = None,
    refresh_token: str = None,
    bot: bool = False,
):
    owner_id = _resolve_user_id(user_id)
    await save_twitch_tokens(owner_id, token, refresh_token, bot)


async def create_twitch_instance(
    user_id: str | None = None,
    bot: bool = False,
    token: str = None,
    refresh_token: str = None,
):
    global twitch
    global user
    global user_bot
    global twitch_bot

    owner_id = _resolve_user_id(user_id)
    set_active_user_id(owner_id)

    if token is None or refresh_token is None:
        tokens = await get_tokens(owner_id, bot)
        if tokens:
            token = tokens["token"]
            refresh_token = tokens["refresh_token"]

    if token is None or refresh_token is None:
        raise Exception("No existen tokens de Twitch guardados para este usuario")

    try:
        if bot:
            twitch_bot = await authenticate_twitch(owner_id, token, refresh_token)
            user_bot = await get_profile_users(bot=True)
            await _ensure_twitch_channel(owner_id, user_bot)
            return twitch, twitch_bot, user_bot.id
        twitch = await authenticate_twitch(owner_id, token, refresh_token)
        user = await get_profile_users(bot=False)
        await _ensure_twitch_channel(owner_id, user)
        return twitch, twitch, user.id
    except Exception as e:
        raise Exception(f"Error al crear la instancia de Twitch: {str(e)}")


async def authenticate_twitch(
    user_id: str | None = None, token: str = None, refresh_token: str = None
):
    owner_id = _resolve_user_id(user_id)
    settings = await load_effective_settings(owner_id)
    client_id = settings.get("twitch_client_id")
    client_secret = settings.get("twitch_client_secret")
    if not client_id or not client_secret:
        raise Exception(
            "Faltan twitch_client_id o twitch_client_secret en la configuración del usuario"
        )

    twitch_client = await Twitch(client_id, client_secret)
    try:
        await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
    except UnauthorizedException:
        try:
            print("Token vencido. Renovando...")
            new_tokens = await refresh_access_token(owner_id, refresh_token)
            token = new_tokens["access_token"]
            refresh_token = new_tokens["refresh_token"]
            await save_twitch_tokens(owner_id, token, refresh_token)
            await twitch_client.set_user_authentication(token, USER_SCOPE, refresh_token)
        except Exception as exc:
            print(traceback.format_exc())
            raise Exception(
                "No se pudo autenticar con Twitch. "
                "Verifica que el access token y refresh token pertenezcan a esta app "
                "y que tengan los scopes requeridos."
            ) from exc
    except Exception as exc:
        print(traceback.format_exc())
        raise Exception(f"Falló la autenticación de Twitch: {repr(exc)}") from exc
    return twitch_client


async def _ensure_twitch_channel(user_id: str, twitch_user) -> None:
    settings = await load_effective_settings(user_id)
    if settings.get("twitch_channel"):
        return

    channel_name = (
        getattr(twitch_user, "name", None)
        or getattr(twitch_user, "login", None)
        or getattr(twitch_user, "display_name", None)
    )
    if not channel_name:
        raise Exception("No se pudo determinar el canal de Twitch del usuario")

    await save_effective_settings({"twitch_channel": str(channel_name)}, user_id)


async def get_profile_users(bot: bool = False):
    global twitch
    global twitch_bot
    global user_bot
    global user
    if bot:
        user_bot = await first(twitch_bot.get_users())
        return user_bot
    user = await first(twitch.get_users())
    return user


async def return_twitch_instance(bot: bool = False):
    global twitch
    global twitch_bot
    global user
    global user_bot
    if bot:
        return twitch, twitch_bot, user.id
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
