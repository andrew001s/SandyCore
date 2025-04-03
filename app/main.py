from fastapi import FastAPI, BackgroundTasks
import asyncio
import threading
from app.services.messages import run_bot
from app.services.speech2Text import transcribir_audio

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

@app.get("/start")
async def start_services(service: str, background_tasks: BackgroundTasks):
    if service == "twitch":
        threading.Thread(target=run_bot_thread, daemon=True).start()
        return {"message": "Bot iniciado en segundo plano."}
    elif service == "talk":
        threading.Thread(target=transcribir_audio_thread, daemon=True).start()
        return {"message": "Transcripción de audio iniciada en segundo plano."}
    elif service == "both":
        threading.Thread(target=run_bot_thread, daemon=True).start()
        threading.Thread(target=transcribir_audio_thread, daemon=True).start()
        return {"message": "Bot y transcripción de audio iniciados en segundo plano."}
    else:
        return {"error": "Opción no válida. Usa 'bot', 'audio' o 'both'."}
