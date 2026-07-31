import asyncio
import json
from functools import lru_cache
from typing import Any

from app.core.config import config

_TABLE_USER_SETTINGS = "user_settings"
_TABLE_TWITCH_TOKENS = "twitch_tokens"


def _supabase_credentials() -> tuple[str, str]:
    if not config.SUPABASE_URL:
        raise RuntimeError("Falta SUPABASE_URL en la configuracion")
    if not config.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "Falta SUPABASE_SERVICE_ROLE_KEY (o SUPABASE_SECRET_KEY) en la configuracion"
        )
    return config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY


@lru_cache(maxsize=1)
def _supabase_client():
    url, key = _supabase_credentials()

    from supabase import create_client

    try:
        from supabase.client import ClientOptions
    except ImportError:
        from supabase.lib.client_options import ClientOptions

    return create_client(
        url,
        key,
        options=ClientOptions(
            persist_session=False,
            auto_refresh_token=False,
        ),
    )


def _normalize_json(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise TypeError(f"Formato JSON inesperado: {type(value)!r}")


def initialize_db_sync() -> None:
    return None


async def initialize_db() -> None:
    return None


def upsert_user_settings_sync(user_id: str, settings: dict[str, Any]) -> None:
    client = _supabase_client()
    payload = {
        "user_id": user_id,
        "settings_json": settings,
    }
    client.table(_TABLE_USER_SETTINGS).upsert(
        payload,
        on_conflict="user_id",
    ).execute()


async def upsert_user_settings(user_id: str, settings: dict[str, Any]) -> None:
    await asyncio.to_thread(upsert_user_settings_sync, user_id, settings)


def get_user_settings_sync(user_id: str) -> dict[str, Any] | None:
    client = _supabase_client()
    response = (
        client.table(_TABLE_USER_SETTINGS)
        .select("settings_json")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    return _normalize_json(rows[0].get("settings_json"))


async def get_user_settings(user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_user_settings_sync, user_id)


def save_twitch_tokens_sync(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    client = _supabase_client()
    payload = {
        "user_id": user_id,
        "bot": bool(bot),
        "access_token": token,
        "refresh_token": refresh_token,
    }
    client.table(_TABLE_TWITCH_TOKENS).upsert(
        payload,
        on_conflict="user_id,bot",
    ).execute()


async def save_twitch_tokens(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    await asyncio.to_thread(save_twitch_tokens_sync, user_id, token, refresh_token, bot)


def get_twitch_tokens_sync(user_id: str, bot: bool = False) -> dict[str, str] | None:
    client = _supabase_client()
    response = (
        client.table(_TABLE_TWITCH_TOKENS)
        .select("access_token, refresh_token")
        .eq("user_id", user_id)
        .eq("bot", bool(bot))
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    row = rows[0]
    return {
        "token": row["access_token"],
        "refresh_token": row["refresh_token"],
    }


async def get_twitch_tokens(user_id: str, bot: bool = False) -> dict[str, str] | None:
    return await asyncio.to_thread(get_twitch_tokens_sync, user_id, bot)
