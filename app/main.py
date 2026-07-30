from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketState
from fastapi.responses import JSONResponse

from app.config.cors import configure_cors
from app.controllers.http.gemini_router import router as gemini_router
from app.controllers.http.realtime_router import router as realtime_router
from app.controllers.http.settings_router import router as settings_router
from app.controllers.http.test_router import router as test_router
from app.controllers.http.twitch_router import router as twitch_router
from app.controllers.websocket.websocket_server import handle_websocket

tags_metadata = [
    {"name": "Health", "description": "Verificación de estado de la API."},
    {"name": "Twitch", "description": "Autenticación, tokens y control de servicios de Twitch."},
    {"name": "Settings", "description": "Configuración por usuario guardada en SQLite."},
    {"name": "AI", "description": "Consultas a la capa de IA."},
]

app = FastAPI(
    title="Sandy Core IA API",
    description="API para autenticación con Clerk, persistencia en SQLite y control de Twitch/IA.",
    version="1.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
configure_cors(app)


app.include_router(test_router)
app.include_router(twitch_router)
app.include_router(settings_router)
app.include_router(gemini_router)
app.include_router(realtime_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await handle_websocket(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@app.get("/get-profile")
async def get_profile(bot: bool = False):
    try:
        from app.services.twitch.twitch import get_user_profile

        profile = await get_user_profile(bot)
        return JSONResponse(status_code=200, content={"profile": profile})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
