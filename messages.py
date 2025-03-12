import os
import asyncio
from twitchio.ext import commands
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

TOKEN = os.getenv("TWITCH_TOKEN")
CHANNEL = os.getenv("TWITCH_CHANNEL")

class TwitchBot(commands.Bot):
    def __init__(self):
        # Aquí pasamos el token correctamente y configuramos el canal
        super().__init__(token=TOKEN, prefix="!", initial_channels=[CHANNEL])

    async def event_ready(self):
        print(f'Bot conectado a {CHANNEL}')  # Confirma que el bot se conectó

    async def event_message(self, message):
        if message.echo:  # Evitar que el bot procese sus propios mensajes
            return

        print(f"[{message.author.name}]: {message.content}")  # Mostrar mensaje en consola

        # Puedes hacer algo con el mensaje aquí (por ejemplo, enviarlo a Gemini)

async def run_bot():
    bot = TwitchBot()
    try:
        await bot.start()
    except Exception as e:
        print(f"Error al conectar al bot: {e}")

if __name__ == "__main__":
    asyncio.run(run_bot())
