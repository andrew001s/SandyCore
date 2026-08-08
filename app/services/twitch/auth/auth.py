import asyncio
import traceback
from dataclasses import dataclass

import aiohttp
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, UnauthorizedException

from app.core.config import config
from app.core.runtime import get_active_user_id, set_active_user_id
from app.services.client_settings import load_effective_settings
from app.services.client_settings import save_effective_settings
from app.services.storage.supabase_store import get_twitch_tokens, save_twitch_tokens

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

@dataclass
class TwitchSession:
    """Cliente de Twitch autenticado, siempre atado a un usuario concreto."""

    user_id: str
    bot: bool
    client: Twitch
    profile: object | None = None


# Registro de sesiones por (user_id, bot). Nunca uses un cliente global:
# el proceso atiende a varios usuarios y compartir la instancia hace que
# un cliente reciba el perfil y los datos de otro.
_sessions: dict[tuple[str, bool], TwitchSession] = {}
_session_locks: dict[tuple[str, bool], asyncio.Lock] = {}


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return str(owner_id)


def _session_key(owner_id: str, bot: bool) -> tuple[str, bool]:
    return (str(owner_id), bool(bot))


def _missing_session_message(bot: bool) -> str:
    if bot:
        return "No existe una sesión de bot autenticada para este usuario"
    return "No existe una sesión de Twitch autenticada para este usuario"


def _lock_for(key: tuple[str, bool]) -> asyncio.Lock:
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
    return lock


def _store_session(owner_id: str, bot: bool, client: Twitch) -> TwitchSession:
    key = _session_key(owner_id, bot)
    session = TwitchSession(user_id=str(owner_id), bot=bool(bot), client=client)
    _sessions[key] = session
    return session


async def _get_or_create_session(owner_id: str, bot: bool = False) -> TwitchSession:
    key = _session_key(owner_id, bot)
    session = _sessions.get(key)
    if session is not None:
        return session

    async with _lock_for(key):
        session = _sessions.get(key)
        if session is not None:
            return session

        tokens = await get_tokens(owner_id, bot)
        if not tokens:
            raise Exception(_missing_session_message(bot))
        client = await authenticate_twitch(
            owner_id, tokens["token"], tokens["refresh_token"], bot
        )
        return _store_session(owner_id, bot, client)


def get_session(user_id: str | None = None, bot: bool = False) -> TwitchSession | None:
    """Sesión ya autenticada de este usuario, o None si no hay ninguna en memoria."""
    owner_id = _resolve_user_id(user_id)
    return _sessions.get(_session_key(owner_id, bot))


def get_client(user_id: str | None = None, bot: bool = False):
    session = get_session(user_id, bot)
    return session.client if session else None


def get_broadcaster(user_id: str | None = None, bot: bool = False):
    session = get_session(user_id, bot)
    return session.profile if session else None


async def refresh_access_token(user_id: str, refresh_token: str):
    client_id = config.TWITCH_CLIENT_ID
    client_secret = config.TWITCH_SECRET
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
        client = await authenticate_twitch(owner_id, token, refresh_token, bot)
        await _close_session(owner_id, bot)
        _store_session(owner_id, bot, client)

        profile = await get_profile_users(bot=bot, user_id=owner_id)
        await _ensure_twitch_channel(owner_id, profile)

        broadcaster_session = _sessions.get(_session_key(owner_id, False))
        broadcaster_client = broadcaster_session.client if broadcaster_session else None
        if bot:
            return broadcaster_client, client, profile.id
        return client, client, profile.id
    except Exception as e:
        raise Exception(f"Error al crear la instancia de Twitch: {str(e)}")


async def authenticate_twitch(
    user_id: str | None = None,
    token: str = None,
    refresh_token: str = None,
    bot: bool = False,
):
    owner_id = _resolve_user_id(user_id)
    client_id = config.TWITCH_CLIENT_ID
    client_secret = config.TWITCH_SECRET
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
            await save_twitch_tokens(owner_id, token, refresh_token, bot)
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


async def get_profile_users(bot: bool = False, user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    session = await _get_or_create_session(owner_id, bot)
    profile = await first(session.client.get_users())
    if profile is None:
        raise Exception(_missing_session_message(bot))
    session.profile = profile
    return profile


async def return_twitch_instance(bot: bool = False, user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    broadcaster_session = await _get_or_create_session(owner_id, False)
    if broadcaster_session.profile is None:
        await get_profile_users(bot=False, user_id=owner_id)
    broadcaster_id = getattr(broadcaster_session.profile, "id", None)

    if bot:
        bot_session = await _get_or_create_session(owner_id, True)
        return broadcaster_session.client, bot_session.client, broadcaster_id
    return broadcaster_session.client, broadcaster_session.client, broadcaster_id


async def _close_session(owner_id: str, bot: bool) -> None:
    session = _sessions.pop(_session_key(owner_id, bot), None)
    if session is None:
        return
    try:
        await session.client.close()
    except Exception as exc:
        print(f"[TWITCH AUTH] Error al cerrar la sesión de {owner_id}: {repr(exc)}")


async def close_twitch(user_id: str | None = None):
    """Cierra únicamente las sesiones del usuario indicado."""
    owner_id = _resolve_user_id(user_id)
    for bot in (False, True):
        await _close_session(owner_id, bot)


async def close_all_twitch_sessions():
    """Solo para el apagado del proceso."""
    for key in list(_sessions.keys()):
        await _close_session(key[0], key[1])
