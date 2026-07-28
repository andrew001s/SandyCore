from collections import deque

from pydantic import BaseModel

from app.core.config import config
from app.core.ports.ai_port import AIPort
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
BOT_NAME = config.TWITCH_BOT_ACCOUNT


class Order(BaseModel):
    type: str
    order_name: str | None = None
    order_objective: str | None = None


history_chat: deque[str] = deque(maxlen=10)
_ai_client: AIPort | None = None


def _get_ai_client() -> AIPort:
    global _ai_client
    if _ai_client is not None:
        return _ai_client
    provider = config.AI_PROVIDER
    if provider == "openrouter":
        from app.adapters.openrouter_adapter import OpenRouterAdapter

        _ai_client = OpenRouterAdapter()
    else:
        from app.adapters.gemini_adapter import GeminiAdapter

        _ai_client = GeminiAdapter()
    return _ai_client


async def client_gemini(message: str, prompt: str) -> str:
    client = _get_ai_client()
    context = generate_context()
    full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"
    return await client.generate_text(message, full_prompt)


async def client_gemini_order(message: str, prompt: str) -> Order:
    client = _get_ai_client()
    result = await client.generate_structured(prompt + message, Order)
    return result


def add_to_history(message: str):
    history_chat.append(message)


def generate_context() -> str:
    return "\n".join(history_chat)


async def response_sandy(message: str) -> str:
    add_to_history("user:" + message)
    response = await client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    add_to_history(response)
    return response


async def response_sandy_shandrew(message: str) -> str:
    response_assist = await client_gemini_order(message, prompt=PROMPT_ASSIST)
    print("response_assist", response_assist)
    from app.services.twitch.events.moderation_handler import (
        get_stream_info,
        moderator_actions,
    )

    if response_assist.type == "orden":
        await moderator_actions(
            title=response_assist.order_objective, name=response_assist.order_name
        )
        return await client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    elif response_assist.type == "statistics":
        stadistics = await get_stream_info()
        return await client_gemini(str(stadistics), PROMPT_GET_STATISTICS)
    elif response_assist.type == "interacción":
        add_to_history("shandrew:" + message)
        response = await client_gemini(message, PROMPT_VTUBER_SHANDREW + PERSONALITY)
        add_to_history("bot:" + response)
        return response


async def check_message(message: str) -> str:
    response = await client_gemini(message, PROMPT_MOD)
    return response


async def response_gemini_rewards(message: str) -> str:
    response = await client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_REWARDS
    )
    return response


async def response_gemini_events(message: str) -> str:
    response = await client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_EVENTS
    )
    return response
