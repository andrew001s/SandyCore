import json
from typing import Any


REACTION_EMOTIONS = (
    "happy", "sad", "angry", "surprised", "excited",
    "sleepy", "thinking", "confused", "shy",
)


def allowed_reaction_emotions(settings: dict[str, Any] | None = None) -> tuple[str, ...]:
    settings = settings or {}
    mappings = settings.get("automatic_reaction_mappings") or {}
    scope = settings.get("automatic_reaction_scope") or "pngtuber"
    enabled = []
    for emotion in REACTION_EMOTIONS:
        stored = mappings.get(f"{scope}:{emotion}", mappings.get(emotion))
        try:
            config = json.loads(stored) if isinstance(stored, str) else None
        except (ValueError, TypeError):
            config = None
        if not isinstance(config, dict) or config.get("enabled") is not False:
            enabled.append(emotion)
    return tuple(enabled)


def filter_reaction_decision(reaction, emotion, settings):
    if reaction is True and emotion in allowed_reaction_emotions(settings):
        return True, emotion
    return False, None


def reaction_instruction(settings: dict[str, Any] | None = None) -> str:
    allowed = allowed_reaction_emotions(settings)
    if not allowed:
        return (
            "Todas las emociones visuales están desactivadas. No analices ni infieras "
            "emociones visuales. Termina siempre con [[REACTION:none]]. "
            "El marcador es metadato, no parte de la voz."
        )
    return (
        "Al final, añade [[REACTION:<emotion>]] solo cuando el mensaje provoque una "
        "emoción clara e intensa que merezca una reacción visual especial. "
        "[[REACTION:none]] es la opción habitual: úsala ante mensajes informativos, "
        "saludos, preguntas corrientes o cuando la reacción no aporte algo evidente. "
        "No añadas una emoción por defecto ni deduzcas una solo por el tono del mensaje. "
        f"Emociones permitidas: {', '.join(allowed)}. "
        "Analiza y elige exclusivamente entre estas emociones activadas. "
        "No analices, infieras ni selecciones ninguna emoción fuera de esta lista; "
        "si ninguna corresponde, usa [[REACTION:none]]. "
        "El marcador es metadato, no parte de la voz."
    )
