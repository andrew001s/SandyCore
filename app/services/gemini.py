from collections import deque

from pydantic import BaseModel

from app.core.config import config
from app.core.runtime import get_active_user_id
from app.core.ports.ai_port import AIPort
from app.services.client_settings import load_effective_settings
from app.domain.prompts import (
    PROMPT_ASSIST,
    PROMPT_GET_STATISTICS,
    PROMPT_MOD,
    PROMPT_VTUBER,
    PROMPT_VTUBER_EVENTS,
    PROMPT_VTUBER_REWARDS,
    PROMPT_VTUBER_SHANDREW,
)

PERSONALITY = config.PERSONALITY


class Order(BaseModel):
    type: str
    order_name: str | None = None
    order_objective: str | None = None


history_chat: deque[str] = deque(maxlen=10)
_ai_client_cache: dict[tuple[str, str, str], AIPort] = {}


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
        from app.adapters.openrouter_adapter import OpenRouterAdapter

        client = OpenRouterAdapter(
            api_key=settings["openrouter_api_key"],
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
    add_to_history("user:" + message)
    response = await client_gemini(message, PROMPT_VTUBER + PERSONALITY, user_id)
    add_to_history(response)
    return response


async def response_sandy_shandrew(message: str, user_id: str | None = None) -> str:
    response_assist = await client_gemini_order(message, prompt=PROMPT_ASSIST, user_id=user_id)
    print("response_assist", response_assist)
    from app.services.twitch.events.moderation_handler import (
        get_stream_info,
        moderator_actions,
    )

    if response_assist.type == "orden":
        await moderator_actions(
            title=response_assist.order_objective, name=response_assist.order_name
        )
        return await client_gemini(message, PROMPT_VTUBER + PERSONALITY, user_id)
    elif response_assist.type == "statistics":
        stadistics = await get_stream_info()
        return await client_gemini(str(stadistics), PROMPT_GET_STATISTICS, user_id)
    elif response_assist.type == "interacción":
        add_to_history("shandrew:" + message)
        response = await client_gemini(
            message, PROMPT_VTUBER_SHANDREW + PERSONALITY, user_id
        )
        add_to_history("bot:" + response)
        return response


async def check_message(message: str, user_id: str | None = None) -> str:
    response = await client_gemini(message, PROMPT_MOD, user_id)
    return response


async def response_gemini_rewards(message: str, user_id: str | None = None) -> str:
    response = await client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_REWARDS, user_id
    )
    return response


async def response_gemini_events(message: str, user_id: str | None = None) -> str:
    response = await client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_EVENTS, user_id
    )
    return response
