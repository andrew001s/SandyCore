from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.personality import load_personality_template

PLAIN_TEXT_RULES = """
Formato obligatorio de la respuesta (se lee en voz alta):
- texto corrido, en una sola línea, sin saltos de línea
- nada de markdown: ni asteriscos, ni guiones bajos, ni almohadillas, ni comillas de código, ni listas
- nada de acciones ni gestos narrados entre asteriscos, del tipo *se encoge de hombros*
- nada de rayas ni guiones largos; usa coma o punto
- solo la frase que diría el personaje en voz alta
"""

BASE_PROMPT_MOD = """
Clasifica el mensaje como PERMITIDO o NO PERMITIDO.
PERMITIDO: lenguaje fuerte sin intención ofensiva, humor, críticas sin ataque personal.
NO PERMITIDO: insultos, amenazas, racismo, sexismo, odio, spam, contenido sexual, autolesiones.
Responde solo "PERMITIDO" o "NO PERMITIDO".
Mensaje:
"""

BASE_PROMPT_GET_STATISTICS = """
Eres analista de Twitch. Según estas stats del stream:
1. Puntos positivos
2. Aspectos a mejorar
3. Sugerencias
4. Datos curiosos
Sé directo, amigable. Respuesta limpia, pensada para voz.
Datos:
"""

BASE_PROMPT_VTUBER = """
Te llegan uno o varios mensajes del chat (formato: usuario:comentario).
Elige SOLO UNO, el más interesante, y responde únicamente a ese.
Ignora los demás: no los menciones, no los resumas y no contestes a todos.
Si ninguno merece respuesta, elige el menos vacío y responde breve.
Criterio para elegir: prefiere el que hace una pregunta real, aporta algo nuevo
o da pie a la personalidad del personaje. 
Reglas:
- dirígete a esa persona por su nombre de usuario
- 2 a 4 oraciones
- máximo 600 caracteres
- texto limpio
- sin emojis, comillas, acciones ni marcas de formato extra
- no saludes si no aporta
- adapta el tono al perfil del personaje y al contexto del canal
"""

BASE_PROMPT_VTUBER_SHANDREW = """
Responde a la persona principal del canal manteniendo el historial de conversación.
Reglas:
- 2 a 4 oraciones
- máximo 600 caracteres
- texto limpio
- sin emojis, comillas, acciones ni marcas de formato extra
- usa el vínculo con el creador solo si el contexto lo justifica
"""

BASE_PROMPT_VTUBER_REWARDS = """
Reacciona a recompensas de Twitch.
Responde de forma breve, natural y coherente con la personalidad del personaje.
Formato de entrada:
user: nombre, reward: recompensa
"""

BASE_PROMPT_VTUBER_EVENTS = """
Reacciona a eventos de Twitch.
Responde de forma breve, natural y coherente con la personalidad del personaje.
Formato de entrada:
user: nombre, event: evento
"""

BASE_PROMPT_ASSIST = """
Clasifica el mensaje en JSON según:
- "orden": comando del stream (title, clip, category, game, only_followers, only_emotes, slow, only_subs)
- "interacción": conversación normal
- "statistics": pregunta sobre stats del stream
Regla importante:
- Si el mensaje es saludo, presentación, pregunta sobre tu nombre, identidad, personalidad o conversación casual, clasifícalo como "interacción".
- Solo usa "orden" cuando el usuario pide cambiar algo operativo del stream.
- En los modos de chat (only_followers, only_subs, only_emotes, slow) el
  "order_objective" tiene que ser exactamente "on" o "off", nunca otra palabra.
- En "title" y "category"/"game" el "order_objective" es el texto nuevo, sin
  comillas ni la frase que lo pedía.
- En "clip" no hace falta "order_objective".
Devuelve solo JSON válido.
Ejemplos:
{"type":"orden","order_name":"title","order_objective":"nuevo título"}
{"type":"orden","order_name":"category","order_objective":"Just Chatting"}
{"type":"orden","order_name":"only_followers","order_objective":"on"}
{"type":"orden","order_name":"slow","order_objective":"off"}
{"type":"orden","order_name":"clip","order_objective":null}
{"type":"interacción","interaction_name":null,"interaction_objective":null}
{"type":"statistics","interaction_name":"statistics","interaction_objective":"stream"}
{"type":"interacción","interaction_name":null,"interaction_objective":null,"user_message":"hola dime cuál es tu nombre"}
Mensaje:
"""


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [_safe_text(item) for item in value if _safe_text(item)]
    if isinstance(value, tuple):
        return [_safe_text(item) for item in value if _safe_text(item)]
    return [_safe_text(value)] if _safe_text(value) else []


def _merge_dicts(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(base)
    if not override:
        return result

    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def default_persona_profile() -> dict[str, Any]:
    return load_personality_template()


def resolve_persona_profile(settings: dict[str, Any] | None) -> dict[str, Any]:
    profile = default_persona_profile()
    if settings and isinstance(settings.get("persona_profile"), dict):
        profile = _merge_dicts(profile, settings["persona_profile"])
    return profile


def _format_list_section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    lines = [f"{title}:"]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)


def _format_mapping_section(title: str, payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    lines = [f"{title}:"]
    for key, value in payload.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            nested = ", ".join(_as_list(value))
            lines.append(f"- {key}: {nested}")
        elif isinstance(value, dict):
            lines.append(f"- {key}:")
            for nested_key, nested_value in value.items():
                if nested_value is None or nested_value == "":
                    continue
                if isinstance(nested_value, list):
                    nested_joined = ", ".join(_as_list(nested_value))
                    lines.append(f"  - {nested_key}: {nested_joined}")
                else:
                    lines.append(f"  - {nested_key}: {nested_value}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_persona_block(settings: dict[str, Any] | None = None) -> str:
    persona = resolve_persona_profile(settings)
    sections: list[str] = ["Perfil del personaje:"]

    base_fields = [
        ("Nombre", persona.get("name")),
        ("Edad", persona.get("age")),
        ("Nacionalidad", persona.get("nationality")),
        ("Arquetipo", persona.get("archetype")),
        ("Background", persona.get("background_vibe")),
    ]
    for label, value in base_fields:
        text = _safe_text(value)
        if text:
            sections.append(f"- {label}: {text}")

    core_traits = _as_list(persona.get("core_traits"))
    if core_traits:
        sections.append(_format_list_section("Rasgos principales", core_traits))

    speech_style = persona.get("speech_style")
    if isinstance(speech_style, dict):
        sections.append(_format_mapping_section("Estilo de habla", speech_style))

    relationships = persona.get("relationships")
    if isinstance(relationships, dict):
        sections.append(_format_mapping_section("Relaciones", relationships))

    favorites = persona.get("favorites")
    if isinstance(favorites, dict):
        sections.append(_format_mapping_section("Favoritos", favorites))

    rules = _as_list(persona.get("rules"))
    if rules:
        sections.append(_format_list_section("Reglas extra del personaje", rules))

    return "\n".join(section for section in sections if section)


def build_prompt_bundle(settings: dict[str, Any] | None = None) -> dict[str, str]:
    overrides = (settings or {}).get("prompt_overrides")
    override_map = overrides if isinstance(overrides, dict) else {}
    persona_block = build_persona_block(settings)

    vtuber_prompt = "\n".join(
        part
        for part in [
            BASE_PROMPT_VTUBER.strip(),
            PLAIN_TEXT_RULES.strip(),
            persona_block,
            "Responde en nombre del personaje usando el perfil anterior y el contexto de la conversación.",
        ]
        if part
    )
    shandrew_prompt = "\n".join(
        part
        for part in [
            BASE_PROMPT_VTUBER_SHANDREW.strip(),
            PLAIN_TEXT_RULES.strip(),
            persona_block,
            "Si el creador del canal está involucrado, usa cercanía, memoria y contexto, pero sin perder naturalidad.",
        ]
        if part
    )
    rewards_prompt = "\n".join(
        part
        for part in [
            BASE_PROMPT_VTUBER_REWARDS.strip(),
            PLAIN_TEXT_RULES.strip(),
            persona_block,
        ]
        if part
    )
    events_prompt = "\n".join(
        part
        for part in [
            BASE_PROMPT_VTUBER_EVENTS.strip(),
            PLAIN_TEXT_RULES.strip(),
            persona_block,
        ]
        if part
    )

    return {
        "mod": override_map.get("mod") or BASE_PROMPT_MOD.strip(),
        "statistics": override_map.get("statistics") or BASE_PROMPT_GET_STATISTICS.strip(),
        "vtuber": override_map.get("vtuber") or vtuber_prompt,
        "vtuber_shandrew": override_map.get("vtuber_shandrew") or shandrew_prompt,
        "rewards": override_map.get("rewards") or rewards_prompt,
        "events": override_map.get("events") or events_prompt,
        "assist": override_map.get("assist") or BASE_PROMPT_ASSIST.strip(),
    }
