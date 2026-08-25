from collections import deque
import re
import unicodedata
from typing import Any

from pydantic import BaseModel

from app.core.runtime import get_active_user_id
from app.core.ports.ai_port import AIPort
from app.services.client_settings import load_effective_settings
from app.services.twitch.lifecycle import register_activity_and_monitor
from app.domain.prompts import build_prompt_bundle, resolve_persona_profile


class Order(BaseModel):
    type: str = "interacción"
    order_name: str | None = None
    order_objective: str | None = None


# Historial de conversación por usuario. Con un solo deque global, el contexto
# de un streamer terminaba dentro del prompt de otro.
HISTORY_MAX_LEN = 10
_history_by_user: dict[str, deque[str]] = {}
_ai_client_cache: dict[tuple[str, str, str], AIPort] = {}


def _history_key(user_id: str | None = None) -> str:
    return str(user_id or get_active_user_id() or "__sin_usuario__")


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


# Marcas con las que el modelo abre un turno nuevo. El historial que le pasamos
# tiene forma de transcripción, así que a veces sigue escribiendo el siguiente
# turno además del suyo, repitiendo la respuesta con su propio nombre delante.
_TURN_MARKERS = ("user:", "usuario:", "streamer:", "bot:", "viewer:")


def persona_name(settings: dict[str, Any] | None) -> str:
    profile = resolve_persona_profile(settings)
    name = profile.get("name") if isinstance(profile, dict) else None
    return str(name).strip() if name else ""


# La respuesta se lee en voz alta: no debe traer markdown, saltos de línea ni
# roleo de acciones entre asteriscos. El prompt ya lo pide, pero los modelos lo
# ignoran, así que se limpia de forma determinista.
_BACKTICKS = re.compile(r"`+")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_LINE_PREFIX = re.compile(r"(?m)^[ \t]{0,3}(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+|\d+[.)][ \t]+)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_ROLEPLAY = re.compile(r"\*[^*\n]+\*")
_ITALIC = re.compile(r"_([^_\n]+)_")
_DASHES = re.compile(r"[\u2014\u2013\u2015]")
_LEFTOVER = re.compile(r"[*_`#>]")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?…])")
_WHITESPACE = re.compile(r"\s+")


def strip_formatting(text: str) -> str:
    """Deja la respuesta como texto plano apto para leer en voz alta."""
    if not text:
        return ""

    cleaned = _BACKTICKS.sub("", text)
    cleaned = _MD_LINK.sub(r"\1", cleaned)
    cleaned = _LINE_PREFIX.sub("", cleaned)
    # El énfasis conserva la palabra; la acción entre asteriscos simples es
    # roleo y se elimina entera.
    cleaned = _BOLD.sub(lambda m: m.group(1) or m.group(2), cleaned)
    cleaned = _ROLEPLAY.sub(" ", cleaned)
    cleaned = _ITALIC.sub(r"\1", cleaned)
    cleaned = _DASHES.sub(" ", cleaned)
    cleaned = _LEFTOVER.sub("", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned)
    cleaned = _SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    return cleaned.strip(" ,;:-")


def _sanitize_reply(response: str, name: str | None = None) -> str:
    """Recorta el turno extra que el modelo a veces añade a su propia respuesta."""
    text = (response or "").strip()
    if not text:
        return text

    markers = [m for m in (f"{name}:" if name else "",) if m] + list(_TURN_MARKERS)
    lowered = text.lower()

    # Un prefijo al inicio es solo la etiqueta del turno propio: se quita.
    for marker in markers:
        if lowered.startswith(marker.lower()):
            text = text[len(marker) :].lstrip()
            lowered = text.lower()
            break

    # A partir de ahí, cualquier marca abre un turno que no le toca escribir.
    cut = len(text)
    for marker in markers:
        idx = lowered.find(marker.lower())
        if idx > 0:
            cut = min(cut, idx)
    return strip_formatting(text[:cut])


def build_stop_sequences(name: str | None = None) -> list[str]:
    """Secuencias que impiden al modelo escribir el turno siguiente.

    El nombre del personaje va primero porque es la etiqueta con la que más
    veces reabre la conversación por su cuenta.
    """
    sequences = [f"{name}:"] if name else []
    sequences.extend(_TURN_MARKERS)
    vistos: set[str] = set()
    unicas = []
    for seq in sequences:
        clave = seq.lower()
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(seq)
    return unicas


async def client_gemini(
    message: str,
    prompt: str,
    user_id: str | None = None,
    name: str | None = None,
) -> str:
    client = await _get_ai_client(user_id)
    context = generate_context(user_id)
    # El mensaje NO se repite aquí: los adaptadores ya lo mandan como turno de
    # usuario. Enviarlo también dentro del prompt lo duplicaba en la petición.
    full_prompt = f"{prompt}\nHistorial conversacion: {context}"
    raw = await client.generate_text(
        message, full_prompt, build_stop_sequences(name)
    )
    # El saneador se queda como red: los proveedores no siempre respetan `stop`,
    # y no cubre el caso de la etiqueta al inicio de la respuesta.
    return _sanitize_reply(raw, name)


async def client_gemini_order(
    message: str, prompt: str, user_id: str | None = None
) -> Order:
    client = await _get_ai_client(user_id)
    result = await client.generate_structured(prompt + message, Order)
    return result


def add_to_history(message: str, user_id: str | None = None):
    key = _history_key(user_id)
    history = _history_by_user.get(key)
    if history is None:
        history = deque(maxlen=HISTORY_MAX_LEN)
        _history_by_user[key] = history
    history.append(message)


def generate_context(user_id: str | None = None) -> str:
    return "\n".join(_history_by_user.get(_history_key(user_id), ()))


def clear_history(user_id: str | None = None) -> None:
    _history_by_user.pop(_history_key(user_id), None)


def _record_exchange(
    user_entry: str,
    response: str,
    user_id: str | None = None,
    *,
    bot_prefix: str = "",
) -> None:
    """Registra el turno SOLO si la IA respondió.

    Escribir el mensaje del usuario antes de llamar a la IA dejaba, cuando la
    llamada fallaba, un turno sin respuesta en el historial. Ese residuo se
    reenviaba como contexto en la siguiente petición que sí funcionaba y el
    modelo terminaba contestando de golpe todos los mensajes acumulados.
    """
    if not response:
        return
    add_to_history(user_entry, user_id)
    add_to_history(f"{bot_prefix}{response}", user_id)


async def response_sandy(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["vtuber"], user_id, persona_name(settings))
    _record_exchange("user:" + message, response, user_id)
    await register_activity_and_monitor(user_id)
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
            title=response_assist.order_objective,
            name=response_assist.order_name,
            user_id=user_id,
        )
        response = await client_gemini(message, prompts["vtuber"], user_id, persona_name(settings))
        await register_activity_and_monitor(user_id)
        return response
    elif response_type == "statistics":
        stadistics = await get_stream_info(user_id)
        response = await client_gemini(str(stadistics), prompts["statistics"], user_id, persona_name(settings))
        await register_activity_and_monitor(user_id)
        return response
    elif response_type == "interaccion":
        response = await client_gemini(message, prompts["vtuber_shandrew"], user_id, persona_name(settings))
        _record_exchange("streamer:" + message, response, user_id, bot_prefix="bot:")
        await register_activity_and_monitor(user_id)
        return response

    print(
        f"[GEMINI] response_assist.type inesperado: {getattr(response_assist, 'type', None)!r}"
    )
    response = await client_gemini(message, prompts["vtuber_shandrew"], user_id, persona_name(settings))
    _record_exchange("streamer:" + message, response, user_id, bot_prefix="bot:")
    await register_activity_and_monitor(user_id)
    return response


async def check_message(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["mod"], user_id, persona_name(settings))
    return response


async def response_gemini_rewards(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["rewards"], user_id, persona_name(settings))
    await register_activity_and_monitor(user_id)
    return response


async def response_gemini_events(message: str, user_id: str | None = None) -> str:
    settings = await load_effective_settings(user_id or get_active_user_id())
    prompts = build_prompt_bundle(settings)
    response = await client_gemini(message, prompts["events"], user_id, persona_name(settings))
    await register_activity_and_monitor(user_id)
    return response
