import os

from dotenv import load_dotenv

from app.core.bannedWords import load_banned_words
from app.core.personality import read_file

load_dotenv(override=True)


class Config:
    BANNED_WORDS = load_banned_words()
    PERSONALITY = read_file()
    TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
    TWITCH_SECRET = os.getenv("TWITCH_SECRET")
    TWITCH_REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI")
    SQLITE_PATH = os.getenv("SQLITE_PATH")
    CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")
    CLERK_AUDIENCE = os.getenv("CLERK_AUDIENCE")


config = Config()
