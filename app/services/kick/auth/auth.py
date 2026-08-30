from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import traceback
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import config
from app.core.runtime import get_active_user_id, set_active_user_id
from app.services.client_settings import load_effective_settings
from app.services.client_settings import save_effective_settings
from app.services.storage.supabase_store import (
    get_kick_tokens,
    get_kick_event_subscription as get_kick_event_subscription_store,
    save_kick_tokens,
    save_kick_event_subscription,
)

KICK_SCOPES = [
    "user:read",
    "channel:read",
    "channel:write",
    "channel:rewards:read",
    "channel:rewards:write",
    "chat:write",
    "streamkey:read",
    "events:subscribe",
    "moderation:ban",
    "moderation:chat_message:manage",
    "kicks:read",
]

KICK_WEBHOOK_EVENTS = [
    {"name": "chat.message.sent", "version": 1},
    {"name": "channel.followed", "version": 1},
    {"name": "channel.subscription.new", "version": 1},
    {"name": "channel.subscription.renewal", "version": 1},
    {"name": "channel.subscription.gifts", "version": 1},
    {"name": "channel.reward.redemption.updated", "version": 1},
    {"name": "kicks.gifted", "version": 1},
    {"name": "livestream.status.updated", "version": 1},
    {"name": "livestream.metadata.updated", "version": 1},
    {"name": "moderation.banned", "version": 1},
]

_kick_public_key_pem: str | None = None


@dataclass
class KickSession:
    """Cliente de Kick autenticado, siempre atado a un usuario concreto."""

    user_id: str
    bot: bool
    client: "KickAPIClient"
    profile: dict | None = None


# Registro de sesiones por (user_id, bot). Nunca uses un cliente global:
# el proceso atiende a varios usuarios y compartir la instancia hace que
# un cliente reciba el perfil y los datos de otro.
_sessions: dict[tuple[str, bool], KickSession] = {}
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
    return "No existe una sesión de Kick autenticada para este usuario"


def _lock_for(key: tuple[str, bool]) -> asyncio.Lock:
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
    return lock


def _store_session(owner_id: str, bot: bool, client: "KickAPIClient") -> KickSession:
    key = _session_key(owner_id, bot)
    session = KickSession(user_id=str(owner_id), bot=bool(bot), client=client)
    _sessions[key] = session
    return session


async def _get_or_create_session(owner_id: str, bot: bool = False) -> KickSession:
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
        client = await authenticate_kick(
            owner_id, tokens["token"], tokens["refresh_token"], bot
        )
        return _store_session(owner_id, bot, client)


def get_session(user_id: str | None = None, bot: bool = False) -> KickSession | None:
    """Sesión ya autenticada de este usuario, o None si no hay ninguna en memoria."""
    owner_id = _resolve_user_id(user_id)
    return _sessions.get(_session_key(owner_id, bot))


def get_client(user_id: str | None = None, bot: bool = False):
    session = get_session(user_id, bot)
    return session.client if session else None


def get_broadcaster(user_id: str | None = None, bot: bool = False):
    session = get_session(user_id, bot)
    return session.profile if session else None


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")
    return verifier, challenge


def _normalize_public_key(value: object) -> str:
    if value is None:
        raise Exception("No se pudo obtener la public key de Kick")

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")

    text = str(value).strip()
    if not text:
        raise Exception("No se pudo obtener la public key de Kick")

    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except Exception:
            text = text[1:-1]

    text = text.replace("\\n", "\n").replace("\\r", "\r")
    text = text.strip()
    return text


def build_authorize_url(
    state: str,
    code_challenge: str,
    scopes: list[str] | None = None,
    redirect_uri: str | None = None,
) -> str:
    client_id = config.KICK_CLIENT_ID
    if not client_id:
        raise Exception("Falta KICK_CLIENT_ID en la configuración")

    redirect = redirect_uri or config.KICK_REDIRECT_URI
    if not redirect:
        raise Exception("Falta KICK_REDIRECT_URI en la configuración")

    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "state": state,
        "scope": " ".join(scopes or KICK_SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{config.KICK_OAUTH_BASE_URL}/oauth/authorize?{urlencode(query)}"


@dataclass
class KickAPIClient:
    user_id: str
    access_token: str
    refresh_token: str | None = None
    bot: bool = False

    @property
    def api_base_url(self) -> str:
        return config.KICK_API_BASE_URL.rstrip("/")

    @property
    def oauth_base_url(self) -> str:
        return config.KICK_OAUTH_BASE_URL.rstrip("/")

    def _headers(self, authenticated: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _refresh_if_needed(self) -> None:
        if not self.refresh_token:
            raise Exception("El token de Kick expiró y no hay refresh token disponible")
        new_tokens = await refresh_access_token(self.user_id, self.refresh_token)
        self.access_token = new_tokens["access_token"]
        self.refresh_token = new_tokens["refresh_token"]
        await save_kick_tokens(
            self.user_id, self.access_token, self.refresh_token, self.bot
        )

    async def request_json(
        self,
        method: str,
        path: str,
        params: dict | list[tuple[str, str]] | None = None,
        json: dict | None = None,
        data: dict | None = None,
        authenticated: bool = True,
        retry: bool = True,
    ):
        url = f"{self.api_base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=self._headers(authenticated),
            )

        if response.status_code in (401, 403) and retry and authenticated:
            await self._refresh_if_needed()
            return await self.request_json(
                method,
                path,
                params=params,
                json=json,
                data=data,
                authenticated=authenticated,
                retry=False,
            )

        response.raise_for_status()
        if not response.content:
            return None
        try:
            return response.json()
        except Exception:
            return response.text

    async def get_users(self):
        return await self.request_json("GET", "/public/v1/users")

    async def get_channels(self, slugs: list[str] | None = None):
        params = [("slug", slug) for slug in (slugs or [])] if slugs else None
        return await self.request_json("GET", "/public/v1/channels", params=params)

    async def get_livestreams(self, broadcaster_user_id: list[str] | None = None):
        params = (
            [("broadcaster_user_id", user_id) for user_id in broadcaster_user_id]
            if broadcaster_user_id
            else None
        )
        return await self.request_json("GET", "/public/v1/livestreams", params=params)

    async def send_chat_message(self, content: str, channel_id: str | None = None):
        payload: dict[str, str] = {"content": content}
        if channel_id:
            payload["channel_id"] = str(channel_id)
        return await self.request_json("POST", "/public/v1/chat", json=payload)

    async def delete_chat_message(self, message_id: str):
        return await self.request_json(
            "DELETE", f"/public/v1/chat/{message_id}", authenticated=True
        )

    async def close(self) -> None:
        return None


async def refresh_access_token(user_id: str, refresh_token: str):
    client_id = config.KICK_CLIENT_ID
    client_secret = config.KICK_SECRET
    if not client_id or not client_secret:
        raise Exception(
            "Faltan KICK_CLIENT_ID o KICK_SECRET en la configuración del usuario"
        )

    url = f"{config.KICK_OAUTH_BASE_URL}/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=30.0) as session:
        resp = await session.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to refresh token: {resp.status_code} {resp.text}")
        return resp.json()


async def exchange_authorization_code(
    code: str, code_verifier: str, redirect_uri: str | None = None
):
    client_id = config.KICK_CLIENT_ID
    client_secret = config.KICK_SECRET
    if not client_id or not client_secret:
        raise Exception(
            "Faltan KICK_CLIENT_ID o KICK_SECRET en la configuración del usuario"
        )

    redirect = redirect_uri or config.KICK_REDIRECT_URI
    if not redirect:
        raise Exception("Falta KICK_REDIRECT_URI en la configuración del usuario")

    url = f"{config.KICK_OAUTH_BASE_URL}/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=30.0) as session:
        resp = await session.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to exchange code: {resp.status_code} {resp.text}")
        return resp.json()


async def client_credentials_token():
    client_id = config.KICK_CLIENT_ID
    client_secret = config.KICK_SECRET
    if not client_id or not client_secret:
        raise Exception(
            "Faltan KICK_CLIENT_ID o KICK_SECRET en la configuración del usuario"
        )

    url = f"{config.KICK_OAUTH_BASE_URL}/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=30.0) as session:
        resp = await session.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise Exception(
                f"Failed to create app token: {resp.status_code} {resp.text}"
            )
        return resp.json()


async def introspect_token(token: str):
    url = f"{config.KICK_API_BASE_URL.rstrip('/')}/public/v1/token/introspect"
    data = {"token": token}
    async with httpx.AsyncClient(timeout=30.0) as session:
        resp = await session.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to introspect token: {resp.status_code} {resp.text}")
        return resp.json()


async def get_public_key() -> str:
    global _kick_public_key_pem
    if _kick_public_key_pem:
        return _kick_public_key_pem

    url = f"{config.KICK_API_BASE_URL.rstrip('/')}/public/v1/public-key"
    async with httpx.AsyncClient(timeout=30.0) as session:
        resp = await session.get(url, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            raise Exception(
                f"Failed to fetch Kick public key: {resp.status_code} {resp.text}"
            )
        text = resp.text.strip()
        if "BEGIN PUBLIC KEY" in text:
            _kick_public_key_pem = _normalize_public_key(text)
            return _kick_public_key_pem
        payload = resp.json()
        key = (
            payload.get("public_key")
            or payload.get("publicKey")
            or payload.get("key")
            or payload.get("data")
        )
        _kick_public_key_pem = _normalize_public_key(key)
        return _kick_public_key_pem


async def verify_webhook_signature(
    message_id: str, timestamp: str, body: bytes, signature_b64: str
) -> bool:
    try:
        public_key_pem = await get_public_key()
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signed_payload = f"{message_id}.{timestamp}.".encode("utf-8") + body
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, signed_payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception as exc:
        print(f"[KICK SIGNATURE] Falló verificación de firma: {repr(exc)}")
        return False


async def save_tokens(
    user_id: str | None = None,
    token: str = None,
    refresh_token: str = None,
    bot: bool = False,
):
    owner_id = _resolve_user_id(user_id)
    await save_kick_tokens(owner_id, token, refresh_token, bot)


async def get_tokens(user_id: str | None = None, bot: bool = False):
    owner_id = _resolve_user_id(user_id)
    tokens = await get_kick_tokens(owner_id, bot)
    if tokens:
        return tokens
    return None


async def authenticate_kick(
    user_id: str | None = None,
    token: str = None,
    refresh_token: str = None,
    bot: bool = False,
):
    owner_id = _resolve_user_id(user_id)
    client_id = config.KICK_CLIENT_ID
    client_secret = config.KICK_SECRET
    if not client_id or not client_secret:
        raise Exception(
            "Faltan KICK_CLIENT_ID o KICK_SECRET en la configuración del usuario"
        )

    if token is None or refresh_token is None:
        tokens = await get_tokens(owner_id, bot)
        if tokens:
            token = tokens["token"]
            refresh_token = tokens["refresh_token"]

    if token is None or refresh_token is None:
        raise Exception("No existen tokens de Kick guardados para este usuario")

    return KickAPIClient(owner_id, token, refresh_token, bot)


def _extract_subscription_id(response: object) -> str | None:
    if isinstance(response, dict):
        for key in ("subscription_id", "subscriptionId", "id"):
            value = response.get(key)
            if value:
                return str(value)
        data = response.get("data")
        if isinstance(data, dict):
            for key in ("subscription_id", "subscriptionId", "id"):
                value = data.get(key)
                if value:
                    return str(value)
        if isinstance(data, list) and data:
            first_item = data[0]
            if isinstance(first_item, dict):
                for key in ("subscription_id", "subscriptionId", "id"):
                    value = first_item.get(key)
                    if value:
                        return str(value)
    return None


async def subscribe_chat_message_events(
    user_id: str | None = None, bot: bool = False
) -> dict[str, object]:
    owner_id = _resolve_user_id(user_id)
    client = await authenticate_kick(owner_id, None, None)
    payload = {
        "method": "webhook",
        "events": KICK_WEBHOOK_EVENTS,
    }
    response = await client.request_json(
        "POST",
        "/public/v1/events/subscriptions",
        json=payload,
        authenticated=True,
    )
    
    saved_any = False
    data = response.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                sub_id = item.get("subscription_id") or item.get("id")
                event_name = item.get("name") or item.get("event")
                if sub_id and event_name:
                    await save_kick_event_subscription(
                        owner_id,
                        str(sub_id),
                        str(event_name),
                        bot,
                    )
                    saved_any = True

    if not saved_any:
        subscription_id = _extract_subscription_id(response)
        if subscription_id:
            await save_kick_event_subscription(
                owner_id,
                subscription_id,
                ",".join(event["name"] for event in KICK_WEBHOOK_EVENTS),
                bot,
            )
    return response


async def get_kick_event_subscription(subscription_id: str):
    return await get_kick_event_subscription_store(subscription_id)


def _extract_profile(user_payload):
    if isinstance(user_payload, list):
        user_payload = user_payload[0] if user_payload else None
    if isinstance(user_payload, dict) and "data" in user_payload:
        data = user_payload["data"]
        if isinstance(data, list):
            user_payload = data[0] if data else None
        elif isinstance(data, dict):
            user_payload = data
    return user_payload or {}


async def _ensure_kick_channel(user_id: str, profile: dict) -> None:
    settings = await load_effective_settings(user_id)
    if settings.get("kick_channel"):
        return

    channel_name = (
        profile.get("slug")
        or profile.get("channel_slug")
        or profile.get("username")
        or profile.get("name")
    )
    if not channel_name:
        return

    await save_effective_settings({"kick_channel": str(channel_name)}, user_id)


async def get_profile_users(bot: bool = False, user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    session = await _get_or_create_session(owner_id, bot)
    profile = _extract_profile(await session.client.get_users())
    session.profile = profile
    await _ensure_kick_channel(owner_id, profile)
    return profile


async def create_kick_instance(
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
        raise Exception("No existen tokens de Kick guardados para este usuario")

    await save_tokens(owner_id, token, refresh_token, bot)

    try:
        client = await authenticate_kick(owner_id, token, refresh_token, bot)
        await _close_session(owner_id, bot)
        _store_session(owner_id, bot, client)

        profile = await get_profile_users(bot=bot, user_id=owner_id)

        broadcaster_session = _sessions.get(_session_key(owner_id, False))
        broadcaster_client = broadcaster_session.client if broadcaster_session else None
        if bot:
            return broadcaster_client, client, profile.get("id")
        return client, client, profile.get("id")
    except Exception as e:
        raise Exception(f"Error al crear la instancia de Kick: {str(e)}")


async def return_kick_instance(bot: bool = False, user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    broadcaster_session = await _get_or_create_session(owner_id, False)
    if broadcaster_session.profile is None:
        await get_profile_users(bot=False, user_id=owner_id)

    profile = broadcaster_session.profile
    broadcaster_id = profile.get("id") if isinstance(profile, dict) else None

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
        print(f"[KICK AUTH] Error al cerrar la sesión de {owner_id}: {repr(exc)}")


async def close_kick(user_id: str | None = None):
    """Cierra únicamente las sesiones del usuario indicado."""
    owner_id = _resolve_user_id(user_id)
    for bot in (False, True):
        await _close_session(owner_id, bot)


async def close_all_kick_sessions():
    """Solo para el apagado del proceso."""
    for key in list(_sessions.keys()):
        await _close_session(key[0], key[1])
