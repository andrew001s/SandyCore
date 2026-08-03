import os

from dotenv import load_dotenv

from app.core.bannedWords import load_banned_words
from app.core.personality import read_file

load_dotenv(override=True)


class Config:
    BANNED_WORDS = load_banned_words()
    PERSONALITY = read_file()
    CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
    STREAM_TOKEN_SECRET = os.getenv("STREAM_TOKEN_SECRET") or CLERK_SECRET_KEY
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_KEY")
    )
    TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
    TWITCH_SECRET = os.getenv("TWITCH_SECRET")
    TWITCH_REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI")
    YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
    YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
    YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI")
    KICK_CLIENT_ID = os.getenv("KICK_CLIENT_ID")
    KICK_SECRET = os.getenv("KICK_SECRET")
    KICK_REDIRECT_URI = os.getenv("KICK_REDIRECT_URI")
    KICK_API_BASE_URL = os.getenv("KICK_API_BASE_URL", "https://api.kick.com")
    KICK_OAUTH_BASE_URL = os.getenv("KICK_OAUTH_BASE_URL", "https://id.kick.com")
    KICK_VERIFY_WEBHOOKS = os.getenv("KICK_VERIFY_WEBHOOKS", "true").lower() == "true"
    CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")
    CLERK_AUDIENCE = os.getenv("CLERK_AUDIENCE")
    FRONTEND_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "https://www.sandystudio.net,http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]


config = Config()
