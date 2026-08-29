from typing import Optional

from pydantic import BaseModel


class ClientSettingsModel(BaseModel):
    twitch_channel: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    twitch_bot_account: Optional[str] = None
    youtube_bot_account: Optional[str] = None
    ai_provider: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    stt_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    azure_speech_key: Optional[str] = None
    azure_region: Optional[str] = None
    language: Optional[str] = None
    fish_audio_key: Optional[str] = None
    voice_id: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    youtube_channel_title: Optional[str] = None
    youtube_broadcast_id: Optional[str] = None
    youtube_live_chat_id: Optional[str] = None
    persona_profile: Optional[dict] = None
    prompt_overrides: Optional[dict] = None
    feature_flags: Optional[dict] = None
    custom_banned_words: Optional[list[str]] = None
    custom_banned_symbols: Optional[list[str]] = None
    custom_banned_links: Optional[list[str]] = None
    service_mode: Optional[str] = None
    chunk_size: Optional[int] = None
    onboarding_completed: Optional[bool] = None
