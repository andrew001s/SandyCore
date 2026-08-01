import re

from app.core.config import config
from app.services.client_settings import load_effective_settings, resolve_feature_flags

BANNED_WORDS = config.BANNED_WORDS


async def check_banned_words(message, user_id: str | None = None):
    settings = await load_effective_settings(user_id)
    feature_flags = resolve_feature_flags(settings)
    if not feature_flags.get("moderation", True):
        return False

    message_lower = message.lower()
    words_in_message = set(re.findall(r"\b\w+\b", message_lower))

    user_banned_words = set(
        word.strip().lower()
        for word in (settings.get("custom_banned_words") or [])
        if str(word).strip()
    )
    if BANNED_WORDS.union(user_banned_words).intersection(words_in_message):
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
