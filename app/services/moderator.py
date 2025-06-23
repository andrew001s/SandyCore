import re

from app.core.config import config

BANNED_WORDS = config.BANNED_WORDS


def check_banned_words(message):
    message = message.lower()
    words_in_message = set(re.findall(r"\b\w+\b", message))
    if BANNED_WORDS.intersection(words_in_message):
        return True
    return False
