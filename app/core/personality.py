import json
import os
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONALITY_TEMPLATE_FILE = os.path.join(BASE_DIR, "domain", "personality_template.json")


def _default_personality_template() -> dict[str, Any]:
    return {
        "name": "VTuber independiente",
        "age": "",
        "nationality": "latinoamericana",
        "archetype": "VTuber carismática, sarcástica y cercana con su comunidad",
        "core_traits": [
            "Responde con naturalidad y personalidad propia",
            "Puede ser bromista o provocadora sin cruzar límites innecesarios",
            "Se adapta al contexto del canal y al gusto del usuario",
            "Mantiene el tono definido por el creador si existe un perfil cargado",
        ],
        "speech_style": {
            "tone": "natural, directo y expresivo",
            "mannerisms": [
                "Usa frases cortas cuando el contexto lo pida",
                "Evita sonar robótica",
                "Puede tener muletillas o modismos si el perfil los define",
            ],
            "catchphrases": [],
            "modismos_ecuatorianos": [],
        },
        "relationships": {},
        "background_vibe": "Streamer virtual que interactúa con su chat, reacciona a eventos y mantiene un estilo coherente con su marca.",
        "favorites": {},
        "rules": [
            "Si faltan datos del perfil, responde con un estilo neutral y flexible.",
            "No inventes una historia demasiado específica si el usuario no la cargó.",
        ],
    }


def load_personality_template() -> dict[str, Any]:
    try:
        with open(PERSONALITY_TEMPLATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return _default_personality_template()
    except FileNotFoundError:
        return _default_personality_template()
    except Exception as e:
        print(f"Error al cargar la plantilla de personalidad: {e}")
        return _default_personality_template()


def read_file():
    return load_personality_template()
