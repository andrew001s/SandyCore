import re

from app.core.config import config
from app.services.client_settings import load_effective_settings, resolve_feature_flags

BANNED_WORDS = config.BANNED_WORDS

_ES_PALABRA = re.compile(r"\w+", re.UNICODE)


def _partir(entradas):
    r"""Separa las entradas que son palabras de las que no.

    El mensaje se trocea en palabras (`\b\w+\b`) y luego se cruza con el
    diccionario, así que una entrada como "bit.ly/", "facebook.com" o "🖕" nunca
    podía coincidir: no son palabras y jamás aparecen como token. Esas se buscan
    como fragmento dentro del texto.
    """
    palabras, fragmentos = set(), set()
    for entrada in entradas:
        texto = str(entrada).strip().lower()
        if not texto:
            continue
        (palabras if _ES_PALABRA.fullmatch(texto) else fragmentos).add(texto)
    return palabras, fragmentos


PALABRAS_BASE, FRAGMENTOS_BASE = _partir(BANNED_WORDS)


async def check_banned_words(message, user_id: str | None = None):
    settings = await load_effective_settings(user_id)
    feature_flags = resolve_feature_flags(settings)
    if not feature_flags.get("moderation", True):
        return False

    message_lower = message.lower()
    words_in_message = set(re.findall(r"\b\w+\b", message_lower))

    palabras_usuario, fragmentos_usuario = _partir(
        settings.get("custom_banned_words") or []
    )
    if (PALABRAS_BASE | palabras_usuario) & words_in_message:
        return True

    # Enlaces, dominios y emojis: se buscan tal cual dentro del mensaje, porque
    # no sobreviven al troceado en palabras.
    for fragmento in FRAGMENTOS_BASE | fragmentos_usuario:
        if fragmento in message_lower:
            return True

    for symbol in settings.get("custom_banned_symbols") or []:
        token = str(symbol).strip()
        if token and token in message:
            return True

    for link in settings.get("custom_banned_links") or []:
        token = str(link).strip().lower()
        if token and token in message_lower:
            return True

    return False
