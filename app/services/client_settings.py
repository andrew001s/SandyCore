import os
from typing import Any

from app.core.runtime import get_active_user_id
from app.adapters.gemini_adapter import DEFAULT_GEMINI_MODEL
from app.core.personality import load_personality_template
from app.core.security.secret_crypto import decrypt_secret_map, encrypt_secret_map
from app.services.storage.supabase_store import get_user_settings, upsert_user_settings


SETTINGS_KEYS = {
    "twitch_channel",
    "kick_channel",
    "youtube_channel_id",
    "youtube_channel_title",
    "youtube_broadcast_id",
    "youtube_live_chat_id",
    "youtube_bot_account",
    "gemini_api_key",
    "gemini_model",
    "twitch_bot_account",
    "kick_bot_account",
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
    "service_mode",
    "chunk_size",
    "onboarding_completed",
}

SENSITIVE_SETTING_KEYS = {
    "gemini_api_key",
    "openrouter_api_key",
    "azure_speech_key",
    "fish_audio_key",
}

# Mensajes de chat que se acumulan antes de pedirle una respuesta a la IA.
DEFAULT_CHUNK_SIZE = 3
CHUNK_SIZE_MIN = 1
CHUNK_SIZE_MAX = 10

# El onboarding antiguo guardaba 'fish' como proveedor de TTS. El valor bueno
# es 'fish_audio'; se normaliza al leer y al escribir para que un perfil viejo
# no arrastre el alias aunque nunca se ejecute la migración retroactiva.
TTS_PROVIDER_ALIASES = {"fish": "fish_audio"}

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
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "twitch_bot_account": os.getenv("TWITCH_BOT_ACCOUNT"),
        "kick_bot_account": os.getenv("KICK_BOT_ACCOUNT"),
        "youtube_bot_account": os.getenv("YOUTUBE_BOT_ACCOUNT"),
        "ai_provider": os.getenv("AI_PROVIDER", "gemini"),
        "gemini_model": os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
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
        "youtube_channel_id": None,
        "youtube_channel_title": None,
        "youtube_broadcast_id": None,
        "youtube_live_chat_id": None,
        "prompt_overrides": {},
        "feature_flags": DEFAULT_FEATURE_FLAGS.copy(),
        "custom_banned_words": [],
        "custom_banned_symbols": [],
        "custom_banned_links": [],
        # Solo existe el modo manual: el híbrido arrancaba y paraba servicios
        # por su cuenta y quemaba tokens sin que el cliente lo decidiera.
        "service_mode": "manual",
        "chunk_size": int(os.getenv("CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
        # Vive en la cuenta, no en el navegador: si no, el onboarding reaparece
        # en cada dispositivo, en incógnito y al limpiar el almacenamiento.
        "onboarding_completed": False,
    }


def normalize_tts_provider(value: Any) -> Any:
    if isinstance(value, str):
        return TTS_PROVIDER_ALIASES.get(value.strip().lower(), value)
    return value


def _normalize_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    payload = _defaults()
    if settings:
        for key in SETTINGS_KEYS:
            if key in settings and settings[key] is not None:
                if isinstance(payload.get(key), dict) and isinstance(settings[key], dict):
                    payload[key] = _merge_dicts(payload[key], settings[key])
                else:
                    payload[key] = settings[key]
    payload["tts_provider"] = normalize_tts_provider(payload.get("tts_provider"))
    # Se ignora lo que hubiera guardado: ya no hay otro modo.
    payload["service_mode"] = "manual"
    payload["onboarding_completed"] = bool(payload.get("onboarding_completed"))
    return decrypt_secret_map(payload, SENSITIVE_SETTING_KEYS)


def resolve_chunk_size(settings: dict[str, Any] | None) -> int:
    """Tamaño de lote de mensajes de chat, acotado a un rango usable.

    Un valor fuera de rango o no numérico llega desde ajustes del usuario, así
    que se recorta en vez de reventar el chat en pleno directo.
    """
    raw = (settings or {}).get("chunk_size", DEFAULT_CHUNK_SIZE)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CHUNK_SIZE
    return max(CHUNK_SIZE_MIN, min(CHUNK_SIZE_MAX, value))


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
    current["tts_provider"] = normalize_tts_provider(current.get("tts_provider"))
    current["service_mode"] = "manual"
    current["onboarding_completed"] = bool(current.get("onboarding_completed"))
    await upsert_user_settings(
        owner_id, encrypt_secret_map(current, SENSITIVE_SETTING_KEYS)
    )
    return current
