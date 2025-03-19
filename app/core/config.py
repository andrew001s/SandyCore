import os
from dotenv import load_dotenv
from app.core.bannedWords import load_banned_words
from app.core.personality import read_file

load_dotenv(override=True)
class Config:
    CHANNEL = os.getenv("TWITCH_CHANNEL")
    BANNED_WORDS = load_banned_words()
    PERSONALITY = read_file()
    ID=os.getenv("TWITCH_CLIENT_ID")
    SECRET=os.getenv("TWITCH_SECRET")
    REDIRECT=os.getenv("REDIRECT_URI")
    GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")
    TWITCH_BOT_ACCOUNT=os.getenv("TWITCH_BOT_ACCOUNT")
    FISH_API_KEY=os.getenv("FISH_API_KEY")
    ID_VOICE=os.getenv("ID_VOICE")

config = Config()