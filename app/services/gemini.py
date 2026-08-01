from collections import deque
import unicodedata

from pydantic import BaseModel

from app.core.runtime import get_active_user_id
from app.core.ports.ai_port import AIPort
from app.services.client_settings import load_effective_settings
from app.domain.prompts import build_prompt_bundle


class Order(BaseModel):
    type: str = "interacción"
    order_name: str | None = None
    order_objective: str | None = None


history_chat: deque[str] = deque(maxlen=10)
_ai_client_cache: dict[tuple[str, str, str], AIPort] = {}


def _normalize_label(value: str | None) -> str:
    text = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


async def _get_ai_client(user_id: str | None = None) -> AIPort:
    settings = await load_effective_settings(user_id or get_active_user_id())
    provider = settings["ai_provider"]
    cache_key = (
        provider,
        str(settings.get("gemini_api_key") or settings.get("openrouter_api_key") or ""),
        str(settings.get("openrouter_model") or ""),
    )
    cached = _ai_client_cache.get(cache_key)
    if cached is not None:
        return cached

    if provider == "openrouter":
        openrouter_api_key = settings.get("openrouter_api_key")
        if not openrouter_api_key:
            raise Exception(
                "Falta openrouter_api_key en la configuracion del usuario en Supabase"
            )
        from app.adapters.openrouter_adapter import OpenRouterAdapter

        client = OpenRouterAdapter(
            api_key=openrouter_api_key,
            model=settings["openrouter_model"],
        )
    else:
        from app.adapters.gemini_adapter import GeminiAdapter

        client = GeminiAdapter(api_key=settings["gemini_api_key"])

    _ai_client_cache[cache_key] = client
    return client


async def client_gemini(message: str, prompt: str, user_id: str | None = None) -> str:
    client = await _get_ai_client(user_id)
    context = generate_context()
    full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"
    return await client.generate_text(message, full_prompt)


async def client_gemini_order(
    message: str, prompt: str, user_id: str | None = None
) -> Order:
    client = await _get_ai_client(user_id)
    result = await client.generate_structured(prompt + message, Order)
    return result


def add_to_history(message: str):
    history_chat.append(message)


def generate_context() -> str:
    return "\n".join(history_chat)


async def response_sandy(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    add_to_history("user:" + message)
    response = await client_gemini(message, prompts["vtuber"], user_id)
    add_to_history(response)
    return response


async def response_sandy_shandrew(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response_assist = await client_gemini_order(
        message, prompt=prompts["assist"], user_id=user_id
    )
    print("response_assist", response_assist)
    response_type = _normalize_label(getattr(response_assist, "type", None))
    from app.services.twitch.events.moderation_handler import (
        get_stream_info,
        moderator_actions,
    )

    if response_type == "orden":
        await moderator_actions(
            title=response_assist.order_objective, name=response_assist.order_name
        )
        return await client_gemini(message, prompts["vtuber"], user_id)
    elif response_type == "statistics":
        stadistics = await get_stream_info()
        return await client_gemini(str(stadistics), prompts["statistics"], user_id)
    elif response_type == "interaccion":
        add_to_history("shandrew:" + message)
        response = await client_gemini(message, prompts["vtuber_shandrew"], user_id)
        add_to_history("bot:" + response)
        return response

    print(
        f"[GEMINI] response_assist.type inesperado: {getattr(response_assist, 'type', None)!r}"
    )
    add_to_history("shandrew:" + message)
    response = await client_gemini(message, prompts["vtuber_shandrew"], user_id)
    add_to_history("bot:" + response)
    return response


async def check_message(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["mod"], user_id)
    return response


async def response_gemini_rewards(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["rewards"], user_id)
    return response


async def response_gemini_events(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["events"], user_id)
    return response
