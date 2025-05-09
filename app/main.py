from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import threading
from fastapi.responses import JSONResponse
from app.services.twitch.twitch import run_bot, get_user_profile, close_twitch
from app.services.speech2Text import transcribir_audio, pause, resume, get_status
import app.shared.state as state
from fastapi import Response


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Sandy IA corriendo🚀"}


def run_bot_thread(bot: bool):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot(bot))


def transcribir_audio_thread():
    transcribir_audio()


@app.get("/start")
async def start_services(bot: bool = False):
    try:
        if state.conected:
            return Response(status_code=204)
        state.conected = True
        threading.Thread(target=run_bot_thread, args=(bot,), daemon=True).start()
        if not hasattr(state, "audio_thread_started") or not state.audio_thread_started:
            threading.Thread(target=transcribir_audio_thread, daemon=True).start()
            state.audio_thread_started = True
        return JSONResponse(status_code=200, content={"message": "Servicios iniciados"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/get-profile")
async def get_profile():
    try:
        profile = await get_user_profile()
        return JSONResponse(status_code=200, content={"profile": profile})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stop")
async def stop_services():
    try:
        state.conected = False
        state.is_paused = False
        await close_twitch()
        return JSONResponse(status_code=200, content={"message": "Servicios detenidos"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/pause")
def pause_microphone():
    pause()
    return JSONResponse(
        status_code=200,
        content={"status": "Micrófono pausado", "paused": state.is_paused},
    )


@app.post("/resume")
def resume_microphone():
    resume()
    return JSONResponse(
        status_code=200,
        content={"status": "Micrófono reanudado", "paused": not state.is_paused},
    )


@app.get("/mic-status")
def mic_status():
    get_status()
    return {"status": "activo" if state else "pausado", "paused": not state.is_paused}
