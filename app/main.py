from fastapi import FastAPI, BackgroundTasks
import asyncio
import threading
from app.services.twitch.twitch import run_bot
from app.services.speech2Text import transcribir_audio, check_keypress, pause, resume, get_status


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


@app.post("/pause")
def pause_microphone():
    state = pause()
    return {"status": "Micrófono pausado", "paused": state}

@app.post("/resume")
def resume_microphone():
    state = resume()
    return {"status": "Micrófono reanudado", "paused": not state}

@app.get("/mic-status")
def mic_status():
    state = get_status()
    return {"status": "activo" if state else "pausado", "paused": not state}
