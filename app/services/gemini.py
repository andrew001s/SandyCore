from collections import deque

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import config
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
GEMINI_API_KEY = config.GEMINI_API_KEY
BOT_NAME = config.TWITCH_BOT_ACCOUNT


class Order(BaseModel):
    type: str
    order_name: str
    order_objective: str


client = genai.Client(api_key=GEMINI_API_KEY)

history_chat: deque[str] = deque(maxlen=10)


def client_gemini(message: str, prompt: str) -> str:
    try:
        context = generate_context()
        full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"

        chat = client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(system_instruction=full_prompt),
        )

        bot_response = chat.send_message(message)
        return bot_response.text
    except Exception as e:
        print(f"Error en client_gemini: {e}")


def client_gemini_order(message: str, prompt: str) -> Order:
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt + message,
            config={
                "response_mime_type": "application/json",
                "response_schema": Order,
            },
        )
        order: Order = response.parsed
        return order
    except Exception as e:
        print(f"Error en client_gemini_order: {e}")


def add_to_history(message: str):
    history_chat.append(message)


def generate_context() -> str:
    return "\n".join(history_chat)


def response_sandy(message: str) -> str:
    add_to_history("user:" + message)
    response = client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    add_to_history(response)
    return response


async def response_sandy_shandrew(message: str) -> str:
    response_assist = client_gemini_order(message, prompt=PROMPT_ASSIST)
    print("response_assist", response_assist)
    from app.services.twitch.events.moderation_handler import (
        get_stream_info,
        moderator_actions,
    )

    if response_assist.type == "orden":
        await moderator_actions(
            title=response_assist.order_objective, name=response_assist.order_name
        )
        return client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    elif response_assist.type == "statistics":
        stadistics = await get_stream_info()
        return client_gemini(str(stadistics), PROMPT_GET_STATISTICS)
    elif response_assist.type == "interacción":
        add_to_history("shandrew:" + message)
        response = client_gemini(message, PROMPT_VTUBER_SHANDREW + PERSONALITY)
        add_to_history("bot:" + response)
        return response


def check_message(message: str) -> str:
    response = client_gemini(message, PROMPT_MOD)
    return response


def response_gemini_rewards(message: str) -> str:
    response = client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_REWARDS
    )
    return response


def response_gemini_events(message: str) -> str:
    response = client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_EVENTS
    )
    return response
