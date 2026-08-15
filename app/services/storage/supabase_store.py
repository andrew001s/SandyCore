import asyncio
import json
from functools import lru_cache
from typing import Any

from app.core.config import config
from app.core.security.secret_crypto import (
    decrypt_secret,
    encrypt_secret,
    encrypt_secret_map,
)

_TABLE_USER_SETTINGS = "user_settings"
_TABLE_TWITCH_TOKENS = "twitch_tokens"
_TABLE_KICK_TOKENS = "kick_tokens"
_TABLE_KICK_EVENT_SUBSCRIPTIONS = "kick_event_subscriptions"
_TABLE_YOUTUBE_TOKENS = "youtube_tokens"


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
        "access_token": encrypt_secret(token),
        "refresh_token": encrypt_secret(refresh_token),
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
        "token": decrypt_secret(row["access_token"]),
        "refresh_token": decrypt_secret(row["refresh_token"]),
    }


async def get_twitch_tokens(user_id: str, bot: bool = False) -> dict[str, str] | None:
    return await asyncio.to_thread(get_twitch_tokens_sync, user_id, bot)


def save_kick_tokens_sync(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    client = _supabase_client()
    payload = {
        "user_id": user_id,
        "bot": bool(bot),
        "access_token": encrypt_secret(token),
        "refresh_token": encrypt_secret(refresh_token),
    }
    client.table(_TABLE_KICK_TOKENS).upsert(
        payload,
        on_conflict="user_id,bot",
    ).execute()


async def save_kick_tokens(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    await asyncio.to_thread(save_kick_tokens_sync, user_id, token, refresh_token, bot)


def get_kick_tokens_sync(user_id: str, bot: bool = False) -> dict[str, str] | None:
    client = _supabase_client()
    response = (
        client.table(_TABLE_KICK_TOKENS)
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
        "token": decrypt_secret(row["access_token"]),
        "refresh_token": decrypt_secret(row["refresh_token"]),
    }


async def get_kick_tokens(user_id: str, bot: bool = False) -> dict[str, str] | None:
    return await asyncio.to_thread(get_kick_tokens_sync, user_id, bot)


def save_kick_event_subscription_sync(
    user_id: str, subscription_id: str, event_name: str, bot: bool = False
) -> None:
    client = _supabase_client()
    payload = {
        "subscription_id": subscription_id,
        "user_id": user_id,
        "bot": bool(bot),
        "event_name": event_name,
    }
    client.table(_TABLE_KICK_EVENT_SUBSCRIPTIONS).upsert(
        payload,
        on_conflict="subscription_id",
    ).execute()


async def save_kick_event_subscription(
    user_id: str, subscription_id: str, event_name: str, bot: bool = False
) -> None:
    await asyncio.to_thread(
        save_kick_event_subscription_sync, user_id, subscription_id, event_name, bot
    )


def get_kick_event_subscription_sync(subscription_id: str) -> dict[str, Any] | None:
    client = _supabase_client()
    response = (
        client.table(_TABLE_KICK_EVENT_SUBSCRIPTIONS)
        .select("user_id, bot, event_name")
        .eq("subscription_id", subscription_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    return rows[0]


async def get_kick_event_subscription(
    subscription_id: str,
) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_kick_event_subscription_sync, subscription_id)


def save_youtube_tokens_sync(
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: int | None = None,
    scope: str | list[str] | None = None,
    token_type: str | None = None,
    provider_account_id: str | None = None,
    email: str | None = None,
) -> None:
    client = _supabase_client()
    payload = {
        "user_id": user_id,
        "access_token": encrypt_secret(access_token),
        "refresh_token": encrypt_secret(refresh_token),
        "expires_at": expires_at,
        "scope": json.dumps(scope) if isinstance(scope, list) else scope,
        "token_type": token_type,
        "provider_account_id": provider_account_id,
        "email": email,
    }
    client.table(_TABLE_YOUTUBE_TOKENS).upsert(
        payload,
        on_conflict="user_id",
    ).execute()


async def save_youtube_tokens(
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: int | None = None,
    scope: str | list[str] | None = None,
    token_type: str | None = None,
    provider_account_id: str | None = None,
    email: str | None = None,
) -> None:
    await asyncio.to_thread(
        save_youtube_tokens_sync,
        user_id,
        access_token,
        refresh_token,
        expires_at,
        scope,
        token_type,
        provider_account_id,
        email,
    )


def get_youtube_tokens_sync(user_id: str) -> dict[str, Any] | None:
    client = _supabase_client()
    response = (
        client.table(_TABLE_YOUTUBE_TOKENS)
        .select(
            "access_token, refresh_token, expires_at, scope, token_type, provider_account_id, email"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    row = rows[0]
    scope = row.get("scope")
    if isinstance(scope, str):
        try:
            scope = json.loads(scope)
        except Exception:
            pass
    return {
        "token": decrypt_secret(row.get("access_token")),
        "refresh_token": decrypt_secret(row.get("refresh_token")),
        "expires_at": row.get("expires_at"),
        "scope": scope,
        "token_type": row.get("token_type"),
        "provider_account_id": row.get("provider_account_id"),
        "email": row.get("email"),
    }


async def get_youtube_tokens(user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_youtube_tokens_sync, user_id)


def delete_youtube_tokens_sync(user_id: str) -> None:
    client = _supabase_client()
    client.table(_TABLE_YOUTUBE_TOKENS).delete().eq("user_id", user_id).execute()


async def delete_youtube_tokens(user_id: str) -> None:
    await asyncio.to_thread(delete_youtube_tokens_sync, user_id)


def backfill_encrypted_secrets_sync() -> dict[str, int]:
    client = _supabase_client()
    stats = {
        "user_settings": 0,
        "twitch_tokens": 0,
        "kick_tokens": 0,
        "youtube_tokens": 0,
    }

    user_settings_rows = (
        client.table(_TABLE_USER_SETTINGS).select("user_id, settings_json").execute()
    )
    for row in getattr(user_settings_rows, "data", None) or []:
        settings = _normalize_json(row.get("settings_json"))
        encrypted_settings = encrypt_secret_map(
            settings,
            {
                "gemini_api_key",
                "openrouter_api_key",
                "azure_speech_key",
                "fish_audio_key",
            },
        )
        if encrypted_settings != settings:
            client.table(_TABLE_USER_SETTINGS).upsert(
                {
                    "user_id": row["user_id"],
                    "settings_json": encrypted_settings,
                },
                on_conflict="user_id",
            ).execute()
            stats["user_settings"] += 1

    twitch_rows = (
        client.table(_TABLE_TWITCH_TOKENS)
        .select("user_id, bot, access_token, refresh_token")
        .execute()
    )
    for row in getattr(twitch_rows, "data", None) or []:
        client.table(_TABLE_TWITCH_TOKENS).upsert(
            {
                "user_id": row["user_id"],
                "bot": bool(row.get("bot")),
                "access_token": encrypt_secret(row.get("access_token")),
                "refresh_token": encrypt_secret(row.get("refresh_token")),
            },
            on_conflict="user_id,bot",
        ).execute()
        stats["twitch_tokens"] += 1

    kick_rows = (
        client.table(_TABLE_KICK_TOKENS)
        .select("user_id, bot, access_token, refresh_token")
        .execute()
    )
    for row in getattr(kick_rows, "data", None) or []:
        client.table(_TABLE_KICK_TOKENS).upsert(
            {
                "user_id": row["user_id"],
                "bot": bool(row.get("bot")),
                "access_token": encrypt_secret(row.get("access_token")),
                "refresh_token": encrypt_secret(row.get("refresh_token")),
            },
            on_conflict="user_id,bot",
        ).execute()
        stats["kick_tokens"] += 1

    youtube_rows = (
        client.table(_TABLE_YOUTUBE_TOKENS)
        .select("user_id, access_token, refresh_token")
        .execute()
    )
    for row in getattr(youtube_rows, "data", None) or []:
        client.table(_TABLE_YOUTUBE_TOKENS).upsert(
            {
                "user_id": row["user_id"],
                "access_token": encrypt_secret(row.get("access_token")),
                "refresh_token": encrypt_secret(row.get("refresh_token")),
            },
            on_conflict="user_id",
        ).execute()
        stats["youtube_tokens"] += 1

    return stats


async def backfill_encrypted_secrets() -> dict[str, int]:
    return await asyncio.to_thread(backfill_encrypted_secrets_sync)
