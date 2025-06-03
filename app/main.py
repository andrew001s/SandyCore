from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

import app.shared.state as state
from app.config.cors import configure_cors
from app.controllers.http.gemini_router import router as gemini_router
from app.controllers.http.test_router import router as test_router
from app.controllers.http.twitch_router import router as twitch_router
from app.controllers.websocket.websocket_server import handle_websocket
from app.services.speech2Text import pause, resume
from app.services.twitch.twitch import get_user_profile

app = FastAPI()
configure_cors(app)


app.include_router(test_router)
app.include_router(twitch_router)
app.include_router(gemini_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await handle_websocket(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket.client_state != WebSocket.DISCONNECTED:
            await websocket.close()


@app.get("/get-profile")
async def get_profile(bot: bool = False):
    try:
        profile = await get_user_profile(bot)
        return JSONResponse(status_code=200, content={"profile": profile})
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
