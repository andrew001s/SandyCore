import os
Base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Personality_file = os.path.join(Base_dir, "data", "personality.txt")

def read_file():
    try:
        with open(Personality_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error al cargar la personalidad: {e}")
        return None