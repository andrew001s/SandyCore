import os
from typing import Any

from app.core.runtime import get_active_user_id
from app.core.personality import load_personality_template
from app.services.storage.supabase_store import get_user_settings, upsert_user_settings


SETTINGS_KEYS = {
    "twitch_channel",
    "gemini_api_key",
    "twitch_bot_account",
    "ai_provider",
    "openrouter_api_key",
    "openrouter_model",
    "stt_provider",
    "tts_provider",
    "azure_speech_key",
    "azure_region",
    "language",
    "fish_audio_key",
    "voice_id",
    "persona_profile",
    "prompt_overrides",
    "feature_flags",
    "custom_banned_words",
    "custom_banned_symbols",
    "custom_banned_links",
}

DEFAULT_FEATURE_FLAGS = {
    "chat_replies": True,
    "voice_replies": True,
    "events": True,
    "rewards": True,
    "moderation": True,
    "assist": True,
}


def _merge_dicts(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(base)
    if not override:
        return payload

    for key, value in override.items():
        if isinstance(payload.get(key), dict) and isinstance(value, dict):
            payload[key] = _merge_dicts(payload[key], value)
        elif value is not None:
            payload[key] = value
    return payload


def _defaults() -> dict[str, Any]:
    return {
        "twitch_channel": os.getenv("TWITCH_CHANNEL"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "twitch_bot_account": os.getenv("TWITCH_BOT_ACCOUNT"),
        "ai_provider": os.getenv("AI_PROVIDER", "gemini"),
        "openrouter_model": os.getenv(
            "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
        ),
        "stt_provider": os.getenv("STT_PROVIDER", "azure"),
        "tts_provider": os.getenv("TTS_PROVIDER", "fish_audio"),
        "azure_speech_key": os.getenv("AZURE_SPEECH_KEY"),
        "azure_region": os.getenv("AZURE_REGION"),
        "language": os.getenv("LANGUAGE", "es-ES"),
        "fish_audio_key": os.getenv("FISH_AUDIO_KEY"),
        "voice_id": os.getenv("VOICE_ID"),
        "persona_profile": load_personality_template(),
        "prompt_overrides": {},
        "feature_flags": DEFAULT_FEATURE_FLAGS.copy(),
        "custom_banned_words": [],
        "custom_banned_symbols": [],
        "custom_banned_links": [],
    }


def _normalize_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    payload = _defaults()
    if settings:
        for key in SETTINGS_KEYS:
            if key in settings and settings[key] is not None:
                if isinstance(payload.get(key), dict) and isinstance(settings[key], dict):
                    payload[key] = _merge_dicts(payload[key], settings[key])
                else:
                    payload[key] = settings[key]
    return payload


def resolve_feature_flags(settings: dict[str, Any] | None) -> dict[str, bool]:
    current = _defaults()["feature_flags"]
    if not settings:
        return current
    incoming = settings.get("feature_flags")
    if isinstance(incoming, dict):
        for key, value in incoming.items():
            if value is not None:
                current[key] = bool(value)
    return current


async def load_effective_settings(user_id: str | None = None) -> dict[str, Any]:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        return _defaults()
    stored = await get_user_settings(owner_id)
    return _normalize_settings(stored)


async def save_effective_settings(
    settings: dict[str, Any], user_id: str | None = None
) -> dict[str, Any]:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise ValueError("No hay un usuario activo para guardar la configuración")
    current = await load_effective_settings(owner_id)
    current.update(
        {key: value for key, value in settings.items() if key in SETTINGS_KEYS}
    )
    await upsert_user_settings(owner_id, current)
    return current
