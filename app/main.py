from fastapi import FastAPI, BackgroundTasks
import asyncio
import threading
from app.services.twitch.twitch import run_bot
from app.services.speech2Text import transcribir_audio, check_keypress

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Twitch Chat Bot corriendo con FastAPI 🚀"}

def run_bot_thread():
    loop = asyncio.new_event_loop() 
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot()) 

def transcribir_audio_thread():
    transcribir_audio()

def check_keypress_thread():
    check_keypress()
    

@app.get("/start")
async def start_services():
    try:
        threading.Thread(target=run_bot_thread, daemon=True).start()
        threading.Thread(target=check_keypress_thread, daemon=True).start()
        threading.Thread(target=transcribir_audio_thread, daemon=True).start()
        return {"message": "Servicios iniciados"}
    except Exception as e:
        return {"error": str(e)}

