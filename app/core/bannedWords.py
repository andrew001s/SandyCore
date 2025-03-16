import json
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNED_WORDS_FILE = os.path.join(BASE_DIR,"data", "banned_words.json")

def load_banned_words():
    try:
        with open(BANNED_WORDS_FILE, "r",encoding="utf-8") as f:
            data= json.load(f)
            banned_words = set()
            for category, words in data.items():
                banned_words.update(words)
            return banned_words
    except Exception as e:
        print(f"Error al cargar las palabras prohibidas: {e}")
        return None
    