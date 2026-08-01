from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
import re


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str | None) -> str:
    return (text or "").strip().lower()


def _infer_emotion(text: str | None, fallback: str = "neutral") -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return fallback

    anger_markers = [
        "chucha",
        "pendej",
        "molest",
        "odio",
        "calla",
        "vete",
        "imbecil",
        "idiot",
        "basura",
        "ridicul",
        "asco",
        "sapo",
        "maldito",
    ]
    sad_markers = ["triste", "decepcion", "mal", "llorar", "pena", "vacío", "vacio"]
    excited_markers = ["wow", "increible", "increíble", "genial", "brutal", "fuego", "🔥"]
    confused_markers = ["?", "no entiendo", "qué", "que pasó", "que pasa", "como así", "por qué", "porque"]
    surprised_markers = ["!", "qué", "que", "no puede ser", "en serio", "wow", "wtf"]
    shy_markers = ["jeje", "jaja", "me da pena", "verg", "vergüenza", "timid"]
    sleepy_markers = ["sueño", "cansado", "cansada", "dormir", "zzz", "agotado"]
    thinking_markers = ["veamos", "analizando", "pienso", "creo que", "tal vez", "quizá", "quizas"]
    happy_markers = ["gracias", "hola", "buenas", "bien", "amor", "quiero", "feliz", "amistad", "te quiero"]

    if any(marker in normalized for marker in anger_markers):
        return "angry"
    if any(marker in normalized for marker in sad_markers):
        return "sad"
    if any(marker in normalized for marker in excited_markers):
        return "excited"
    if any(marker in normalized for marker in surprised_markers):
        return "surprised"
    if any(marker in normalized for marker in confused_markers):
        return "confused"
    if any(marker in normalized for marker in shy_markers):
        return "shy"
    if any(marker in normalized for marker in sleepy_markers):
        return "sleepy"
    if any(marker in normalized for marker in thinking_markers):
        return "thinking"
    if any(marker in normalized for marker in happy_markers):
        return "happy"
    return fallback


def _infer_intensity(text: str | None, emotion: str, base: float) -> float:
    normalized = _normalize_text(text)
    intensity = base

    if emotion in {"angry", "excited", "surprised"}:
        intensity = max(intensity, 0.75)
    elif emotion in {"sad", "confused", "thinking", "shy", "sleepy"}:
        intensity = max(intensity, 0.35)
    elif emotion in {"happy"}:
        intensity = max(intensity, 0.55)

    if "!!" in normalized:
        intensity = min(1.0, intensity + 0.15)
    if "??" in normalized:
        intensity = min(1.0, intensity + 0.08)
    if len(normalized) > 120:
        intensity = min(intensity, 0.65)
    return max(0.0, min(1.0, intensity))


def _infer_speech_style(emotion: str, text: str | None = None) -> str:
    if emotion == "angry":
        return "angry"
    if emotion == "excited":
        return "excited"
    if emotion in {"sad", "sleepy"}:
        return "calm"
    if emotion == "thinking":
        return "serious"
    if emotion == "confused":
        return "serious"
    if emotion == "shy":
        return "shy"
    if emotion == "surprised":
        return "serious"
    if emotion == "happy":
        return "friendly"
    normalized = _normalize_text(text)
    if "?" in normalized:
        return "serious"
    return "calm"


def _infer_gesture(emotion: str) -> str | None:
    if emotion == "angry":
        return "shake_head"
    if emotion == "excited":
        return "bounce"
    if emotion == "surprised":
        return "lean_back"
    if emotion == "happy":
        return "wave"
    if emotion == "sad":
        return "blink"
    if emotion == "thinking":
        return "nod"
    if emotion == "confused":
        return "shake_head"
    if emotion == "shy":
        return "blink"
    if emotion == "sleepy":
        return "blink"
    return "nod"


def _infer_mouth(emotion: str, text: str | None, speech: bool) -> tuple[float, float]:
    normalized = _normalize_text(text)
    if emotion == "angry":
        return (0.45 if speech else 0.25, 0.0)
    if emotion == "excited":
        return (0.65 if speech else 0.5, 0.35)
    if emotion == "surprised":
        return (0.85 if speech else 0.6, 0.05)
    if emotion == "happy":
        return (0.42 if speech else 0.3, 0.55)
    if emotion == "sad":
        return (0.2, 0.05)
    if emotion == "thinking":
        return (0.18, 0.08)
    if emotion == "confused":
        return (0.3, 0.02)
    if emotion == "shy":
        return (0.22, 0.12)
    if emotion == "sleepy":
        return (0.1, 0.02)
    if "?" in normalized:
        return (0.35 if speech else 0.22, 0.08)
    return (0.35 if speech else 0.15, 0.1)


def _base_event(
    event_type: str,
    *,
    text: str | None = None,
    emotion: str = "neutral",
    intensity: float = 0.5,
    duration_ms: int = 1500,
    speech_style: str | None = None,
    gesture: str | None = None,
    mouth_open: float = 0.3,
    mouth_smile: float = 0.1,
    priority: int = 5,
    interrupt: bool = False,
    expression: str | None = None,
    hotkey: str | None = None,
    scene: str | None = "main",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message_value = text
    return {
        "id": f"{event_type}_{uuid4().hex}",
        "type": event_type,
        "text": text,
        "message": message_value,
        "emotion": emotion,
        "intensity": intensity,
        "durationMs": duration_ms,
        "speechStyle": speech_style,
        "gesture": gesture,
        "mouth": {
            "open": mouth_open,
            "smile": mouth_smile,
        },
        "priority": priority,
        "interrupt": interrupt,
        "expression": expression,
        "hotkey": hotkey,
        "scene": scene,
        "metadata": metadata or {},
        "timestamp": _timestamp(),
    }


def build_speech_event(
    text: str,
    *,
    emotion: str | None = None,
    intensity: float = 0.5,
    duration_ms: int | None = None,
    speech_style: str | None = None,
    gesture: str | None = None,
    mouth_open: float | None = None,
    mouth_smile: float | None = None,
    priority: int = 5,
    interrupt: bool = False,
    expression: str | None = None,
    scene: str = "chat",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_emotion = emotion or _infer_emotion(text, fallback="neutral")
    resolved_intensity = _infer_intensity(text, resolved_emotion, intensity)
    resolved_style = speech_style or _infer_speech_style(resolved_emotion, text)
    resolved_gesture = gesture or _infer_gesture(resolved_emotion)
    inferred_open, inferred_smile = _infer_mouth(resolved_emotion, text, True)
    return _base_event(
        "speech",
        text=text,
        emotion=resolved_emotion,
        intensity=resolved_intensity,
        duration_ms=duration_ms or max(1200, min(5000, len(text) * 45)),
        speech_style=resolved_style,
        gesture=resolved_gesture,
        mouth_open=mouth_open if mouth_open is not None else inferred_open,
        mouth_smile=mouth_smile if mouth_smile is not None else inferred_smile,
        priority=priority,
        interrupt=interrupt,
        expression=expression or resolved_emotion,
        scene=scene,
        metadata=metadata,
    )


def build_reaction_event(
    text: str | None = None,
    *,
    emotion: str | None = None,
    intensity: float = 0.9,
    duration_ms: int = 1200,
    gesture: str | None = None,
    mouth_open: float | None = None,
    mouth_smile: float | None = None,
    priority: int = 8,
    interrupt: bool = True,
    expression: str | None = None,
    scene: str = "reaction",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_emotion = emotion or _infer_emotion(text, fallback="surprised")
    resolved_intensity = _infer_intensity(text, resolved_emotion, intensity)
    resolved_gesture = gesture or _infer_gesture(resolved_emotion)
    inferred_open, inferred_smile = _infer_mouth(resolved_emotion, text, False)
    return _base_event(
        "reaction",
        text=text,
        emotion=resolved_emotion,
        intensity=resolved_intensity,
        duration_ms=duration_ms,
        speech_style=None,
        gesture=resolved_gesture,
        mouth_open=mouth_open if mouth_open is not None else inferred_open,
        mouth_smile=mouth_smile if mouth_smile is not None else inferred_smile,
        priority=priority,
        interrupt=interrupt,
        expression=expression or resolved_emotion,
        scene=scene,
        metadata=metadata,
    )


def build_idle_event(
    *,
    emotion: str | None = None,
    intensity: float = 0.1,
    duration_ms: int = 5000,
    mouth_open: float | None = None,
    mouth_smile: float | None = None,
    priority: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_emotion = emotion or "neutral"
    inferred_open, inferred_smile = _infer_mouth(resolved_emotion, None, False)
    return _base_event(
        "idle",
        emotion=resolved_emotion,
        intensity=intensity,
        duration_ms=duration_ms,
        mouth_open=mouth_open if mouth_open is not None else inferred_open,
        mouth_smile=mouth_smile if mouth_smile is not None else inferred_smile,
        priority=priority,
        interrupt=False,
        scene="idle",
        metadata=metadata,
    )


def build_system_event(
    message: str,
    *,
    priority: int = 10,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = metadata.copy() if metadata else {}
    event = _base_event(
        "system",
        text=message,
        emotion="neutral",
        intensity=0.2,
        duration_ms=1000,
        priority=priority,
        interrupt=True,
        scene="system",
        metadata=payload,
    )
    event["message"] = message
    return event


def build_action_event(
    text: str | None = None,
    *,
    hotkey: str | None = None,
    expression: str | None = None,
    gesture: str | None = None,
    priority: int = 10,
    interrupt: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _base_event(
        "action",
        text=text,
        emotion="neutral",
        intensity=0.5,
        duration_ms=1000,
        gesture=gesture,
        priority=priority,
        interrupt=interrupt,
        expression=expression,
        hotkey=hotkey,
        scene="main",
        metadata=metadata,
    )
