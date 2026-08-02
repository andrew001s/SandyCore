from __future__ import annotations

import base64
import hashlib
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

kick = None
user = None
kick_bot = None
user_bot = None
_kick_public_key_pem: str | None = None


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return owner_id


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")
    return verifier, challenge


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
            self.user_id, self.access_token, self.refresh_token, False
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
            _kick_public_key_pem = text
            return text
        payload = resp.json()
        key = (
            payload.get("public_key")
            or payload.get("publicKey")
            or payload.get("key")
            or payload.get("data")
        )
        if not key:
            raise Exception("No se pudo obtener la public key de Kick")
        _kick_public_key_pem = str(key)
        return _kick_public_key_pem


async def verify_webhook_signature(
    message_id: str, timestamp: str, body: bytes, signature_b64: str
) -> bool:
    public_key_pem = await get_public_key()
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    signed_payload = f"{message_id}.{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    signature = base64.b64decode(signature_b64)
    try:
        public_key.verify(signature, signed_payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
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
    user_id: str | None = None, token: str = None, refresh_token: str = None
):
    owner_id = _resolve_user_id(user_id)
    client_id = config.KICK_CLIENT_ID
    client_secret = config.KICK_SECRET
    if not client_id or not client_secret:
        raise Exception(
            "Faltan KICK_CLIENT_ID o KICK_SECRET en la configuración del usuario"
        )

    if token is None or refresh_token is None:
        tokens = await get_tokens(owner_id)
        if tokens:
            token = tokens["token"]
            refresh_token = tokens["refresh_token"]

    if token is None or refresh_token is None:
        raise Exception("No existen tokens de Kick guardados para este usuario")

    return KickAPIClient(owner_id, token, refresh_token)


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
        "events": [{"name": "chat.message.sent", "version": 1}],
    }
    response = await client.request_json(
        "POST",
        "/public/v1/events/subscriptions",
        json=payload,
        authenticated=True,
    )
    subscription_id = _extract_subscription_id(response)
    if subscription_id:
        await save_kick_event_subscription(owner_id, subscription_id, "chat.message.sent", bot)
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
    global kick
    global kick_bot
    global user_bot
    global user
    owner_id = _resolve_user_id(user_id)
    if bot:
        if kick_bot is None:
            tokens = await get_tokens(owner_id, True)
            if not tokens:
                raise Exception("No existe una sesión de bot autenticada para este usuario")
            kick_bot = await authenticate_kick(
                owner_id, tokens["token"], tokens["refresh_token"]
            )
        profile = _extract_profile(await kick_bot.get_users())
        user_bot = profile
        await _ensure_kick_channel(owner_id, profile)
        return profile

    if kick is None:
        tokens = await get_tokens(owner_id, False)
        if not tokens:
            raise Exception("No existe una sesión de Kick autenticada para este usuario")
        kick = await authenticate_kick(owner_id, tokens["token"], tokens["refresh_token"])

    profile = _extract_profile(await kick.get_users())
    user = profile
    await _ensure_kick_channel(owner_id, profile)
    return profile


async def create_kick_instance(
    user_id: str | None = None,
    bot: bool = False,
    token: str = None,
    refresh_token: str = None,
):
    global kick
    global user
    global user_bot
    global kick_bot

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
        if bot:
            kick_bot = await authenticate_kick(owner_id, token, refresh_token)
            profile = await get_profile_users(bot=True)
            return kick, kick_bot, profile.get("id")
        kick = await authenticate_kick(owner_id, token, refresh_token)
        profile = await get_profile_users(bot=False)
        return kick, kick, profile.get("id")
    except Exception as e:
        raise Exception(f"Error al crear la instancia de Kick: {str(e)}")


async def return_kick_instance(bot: bool = False):
    global kick
    global kick_bot
    global user
    global user_bot
    if bot:
        return kick, kick_bot, (user.get("id") if isinstance(user, dict) else None)
    return kick, kick, (user.get("id") if isinstance(user, dict) else None)


async def close_kick():
    global kick
    global kick_bot
    global user
    global user_bot
    if kick:
        await kick.close()
    if kick_bot:
        await kick_bot.close()
    kick = None
    kick_bot = None
    user = None
    user_bot = None
