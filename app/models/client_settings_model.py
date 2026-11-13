from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


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
    chat_trigger_mode: Optional[Literal["batch", "command"]] = None
    chat_command: Optional[str] = Field(default=None, max_length=32)
    onboarding_completed: Optional[bool] = None
    vrm_trigger_rules: Optional[list[dict]] = None
    automatic_reaction_mappings: Optional[dict[str, str]] = None
    automatic_reaction_scope: Optional[Literal["pngtuber", "live2d", "vrm", "vtubestudio"]] = None
    expression_hotkeys: Optional[dict[Annotated[str, Field(max_length=512)], Annotated[str, Field(max_length=80)]]] = Field(default=None, max_length=256)
    expression_intensities: Optional[dict[Annotated[str, Field(max_length=512)], Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]]] = Field(default=None, max_length=256)
